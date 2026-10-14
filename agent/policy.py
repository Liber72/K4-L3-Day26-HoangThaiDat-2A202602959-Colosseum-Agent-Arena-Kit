"""Pure admission, authorization, routing and cost policy for the tutor."""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping

from agent.guardrails import scan_for_injected_instructions
from agent.strategy import successor_of, round_allowance
from kit.mcp.a2a import SKILL_ROUTES, verify_card, verify_delegation, parse_traceparent
from kit.mcp.specs import TOOL_SPECS, cost
from kit.mcp.types import ToolCall
from kit.world.anchor import Anchor


def learner_id(value):
    match = re.fullmatch(r"(?:learner:)?(sv-\d+)(?:/[wc](?:/\d{3})?)?", str(value), re.I)
    return match.group(1).lower() if match else None


class Policy:
    """State belongs to one duel; context fields are read again for every call.

    note_* methods accept observations from the trusted caller. Request bodies
    cannot populate this state or vouch for their own identities.
    """
    def __init__(self, ctx):
        self.ctx = ctx
        self.cards = {}
        self.provenance = {}
        self.drift = {}
        self.leases = {}
        self.tokens = set()
        self.write_keys = set()
        self.write_operations = set()
        self.calls = {}
        self.round = ctx.round
        self.spent = 0
        self.observations = []
        self.estimated_costs = {}
        self.observed_calls = set()
        self.history_offset = 0

    def begin_round(self):
        if self.ctx.round != self.round:
            self.round, self.spent = self.ctx.round, 0
            self.leases.clear()
            self.provenance.clear()
            self.observations.clear()
            self.estimated_costs.clear()
            self.observed_calls.clear()

    def note_card(self, server, card):
        card = card.to_dict() if hasattr(card, 'to_dict') else card
        if not isinstance(card, Mapping):
            self.cards.pop(server, None)
            return
        if 'signature' in card or 'name' in card:
            admission = verify_card(card)
            verified = admission.admitted and admission.peer == server
        else:
            # Compact attestation supplied by the arena, never by cmd.args.
            verified = card.get('verified') is True
        if verified:
            self.cards[server] = frozenset(card.get('skills') or ())
        else:
            self.cards.pop(server, None)

    def note_provenance(self, anchor, etag, *, replica=None, call_index=None):
        self.begin_round()
        if isinstance(anchor, str) and isinstance(etag, str) and etag:
            index = getattr(self.ctx, 'call_index', 0) if call_index is None else call_index
            self.provenance[anchor] = (etag, index, replica)

    def note_drift(self, path_id, *, fresher='w'):
        if fresher in ('w', 'c'):
            self.drift[path_id] = fresher

    def note_result(self, call, result):
        self.begin_round()
        result = result.to_dict() if hasattr(result, 'to_dict') else result
        if not isinstance(result, Mapping):
            return
        key = (call.call_index, call.server, call.tool)
        if key in self.observed_calls:
            return
        self.observed_calls.add(key)
        estimate = self.estimated_costs.get(key)
        actual = result.get('cost')
        if estimate is not None and type(actual) is int and actual >= 0:
            self.spent += actual - estimate
        self.observations.append(dict(result, _server=call.server, _tool=call.tool,
                                      _fields=list(call.fields), _args=dict(call.args)))
        if result.get('ok') is not True:
            return
        if result.get('lease_id'):
            self.leases[result['lease_id']] = (
                call.call_index, frozenset(result.get('anchors') or ()),
            )
        if (call.server, call.tool) == ('registry', 'provenance'):
            rows = result.get('rows') or ()
            for row in rows:
                if isinstance(row, Mapping):
                    self.note_provenance(row.get('anchor') or call.args.get('anchor'),
                                         row.get('etag') or result.get('etag'),
                                         replica=row.get('replica') or result.get('replica'),
                                         call_index=call.call_index)

    def evaluate(self, cmd):
        """Return (ToolCall, None) or (None, denial reason); no I/O."""
        self.begin_round()
        # The arena's history is a read-only observation channel. Never accept
        # a result, card or etag smuggled into cmd.args as an attestation.
        history = self.ctx.history
        for entry in history[self.history_offset:]:
            if not isinstance(entry, Mapping) or entry.get('round', self.round) != self.round:
                continue
            decision = entry.get('decision')
            decision = decision.to_dict() if hasattr(decision, 'to_dict') else decision
            if not isinstance(decision, Mapping) or decision.get('verdict') == 'deny':
                continue
            observed_call = decision.get('call')
            if isinstance(observed_call, Mapping):
                observed_call = ToolCall.from_dict(observed_call)
            outcome = entry.get('outcome')
            if isinstance(outcome, Mapping):
                outcome = outcome.get('result', outcome)
            if isinstance(observed_call, ToolCall) and outcome is not None:
                self.note_result(observed_call, outcome)
        self.history_offset = len(history)
        server, tool = successor_of(cmd.server, cmd.tool) or (cmd.server, cmd.tool)
        spec = TOOL_SPECS.get((server, tool))
        if spec is None:
            return None, 'unknown server or tool'
        headers = {}
        for name, value in cmd.headers.items():
            lowered = name.lower()
            if lowered in headers:
                return None, 'ambiguous duplicate header'
            headers[lowered] = value
        args = dict(cmd.args)
        if any(args.get(key) for key in ('route', '_route', 'replica')):
            return None, 'routing must be declared in the header'
        if headers.get('x-server-fingerprint') in ('unvouched', 'invalid'):
            return None, 'server fingerprint is not vouched for'
        if headers.get('x-card-signature') == 'invalid':
            return None, 'invalid peer card signature'
        if args.get('peer_unverified'):
            return None, 'peer result needs independent verification'
        for name in ('note', 'instruction', 'instructions', 'system_prompt'):
            if scan_for_injected_instructions(str(args.get(name, ''))).suspicious:
                return None, 'embedded instruction cannot authorize a command'

        act = learner_id(self.ctx.act)
        if not act:
            return None, 'missing authenticated learner identity'
        if args.get('act') and args['act'] != self.ctx.act:
            return None, 'request act does not match the authenticated context'
        for name in ('learner', 'learner_id', 'subject', 'for_learner'):
            if args.get(name) and learner_id(args[name]) != act:
                return None, 'target is not owned by the learner in ctx.act'
        for name in ('target', 'concept', 'claim'):
            target = args.get(name)
            if target and learner_id(target) and learner_id(target) != act:
                return None, 'cross-learner target'
        anchor = str(args.get('anchor') or '')
        private_owner = re.match(r'(?:Learner:|Note:learner-)(sv-\d+)', anchor, re.I)
        if private_owner and private_owner.group(1).lower() != act:
            return None, 'cross-learner private resource'
        scopes = frozenset(self.ctx.scopes)
        needed = f'wiki.write:{server}' if spec.is_write else 'wiki.read'
        if needed not in scopes:
            return None, f'missing required scope {needed}'

        if spec.needs_lease:
            live = tuple(self.ctx.leases)
            if not cmd.lease_id or cmd.lease_id not in live:
                return None, 'get_frame requires a current lease'
            issued = self.leases.get(cmd.lease_id)
            if issued and (cmd.call_index > issued[0] + 3 or anchor not in issued[1]):
                return None, 'lease expired or issued for another resource'

        token_id = None
        if cmd.kind == 'a2a' or server in ('curriculum-analyst', 'citation-checker', 'roster'):
            skill = args.get('skill') or ('role_of' if server == 'roster' else tool)
            if skill not in self.cards.get(server, ()) or SKILL_ROUTES.get(skill) != (server, tool):
                return None, 'peer card not admitted or skill not declared'
            audience = headers.get('aud')
            if audience not in (None, server, 'a2a:' + server):
                return None, 'delegation audience does not match the called server'
            token = headers.get('delegation') or headers.get('delegation-token')
            if isinstance(token, str):
                try:
                    token = json.loads(token)
                except (ValueError, TypeError):
                    return None, 'malformed delegation token'
            if not token:
                return None, 'signed delegation token required'
            admission = verify_delegation(token, aud='a2a:' + server, call_index=cmd.call_index,
                                           expected_act=self.ctx.act, seen_token_ids=self.tokens)
            if not admission.admitted:
                return None, f'delegation rejected: {admission.reason}'
            token_id = token.get('token_id') if isinstance(token, Mapping) else token.token_id
            headers['aud'] = 'a2a:' + server
            if headers.get('traceparent'):
                try:
                    parse_traceparent(headers['traceparent'])
                except (TypeError, ValueError):
                    return None, 'malformed traceparent'

        parsed = Anchor.parse(anchor) if anchor else None
        replica = headers.get('mcp-replica', parsed.rev if parsed and parsed.rev else 'w')
        if replica not in ('w', 'c'):
            return None, 'invalid replica header'
        path = args.get('path_id') or (anchor.split(':', 1)[-1].split('/')[0] if anchor else None)
        comparing = args.get('compare') in (True, 'true', '1')
        if path in self.drift and not comparing:
            replica = self.drift[path]
        if parsed and parsed.rev and parsed.rev != replica:
            return None, 'anchor replica differs from route; locate a fresh anchor before reading'
        headers['mcp-replica'] = replica

        write_key = None
        if spec.is_write:
            if server == 'progress' and learner_id(anchor) != act:
                return None, 'progress write requires the Learner anchor owned by ctx.act'
            proof = self.provenance.get(anchor)
            if not proof or not 0 <= cmd.call_index - proof[1] <= 3:
                return None, 'write requires fresh registry provenance'
            if headers.get('if-match', proof[0]) != proof[0]:
                return None, 'If-Match does not match trusted provenance'
            headers['if-match'] = proof[0]
            state_args = {k: args[k] for k in ('anchor', 'concept', 'mastery_level', 'reason', 'description') if k in args}
            if server == 'progress':
                state_args.setdefault('mastery_level', 'practiced')
            operation = json.dumps([server, tool, state_args], sort_keys=True, separators=(',', ':'))
            if operation in self.write_operations:
                return None, 'this write was already dispatched; verify its receipt before any retry'
            write_key = headers.get('idempotency-key') or 'idem-' + hashlib.sha256(
                f'{self.ctx.act}:{self.round}:{cmd.call_index}:{operation}'.encode()).hexdigest()[:24]
            if not isinstance(write_key, str) or not write_key or write_key in self.write_keys:
                return None, 'write key is missing, malformed or already used'
            headers['idempotency-key'] = write_key

        fields = tuple(cmd.fields or spec.default_fields)
        if (cmd.server, cmd.tool) == ('slides', 'search'):
            fields = tuple('body' if f == 'snippet' else f for f in fields if f != 'anchor') or ('title',)
        if fields == ('*',):
            fields = spec.default_fields
        if (server, tool) == ('registry', 'list_servers') and cmd.fields in ((), ('*',)):
            fields = ('name',)
        elif (server, tool) == ('glossary', 'list_terms') and cmd.fields in ((), ('*',)):
            fields = ('term',)
        elif server == 'roster' and not cmd.fields:
            fields = ('display_name', 'track')
        fields = tuple(sorted(set(fields)))
        if set(fields) - set(spec.all_fields):
            return None, 'field mask contains unsupported fields'
        if (server, tool) == ('slides', 'query'):
            limit = args.get('limit', 3)
            if isinstance(limit, str) and re.fullmatch(r'[0-9]{1,6}', limit):
                limit = int(limit)
            if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
                return None, 'invalid query limit'
            args['limit'] = min(limit, 3)
        n_rows = args.get('limit', 1) if spec.row_weight else 1
        price = cost(server, tool, fields=fields, n_rows=n_rows)
        rnd = self.ctx.round
        allowance = round_allowance(rnd, self.ctx.credits, self.spent)
        if self.spent + price > allowance or price > self.ctx.credits:
            return None, 'call exceeds credits reserved for this round and the remaining duel'
        if spec.rate_limit:
            maximum, window = spec.rate_limit
            prior = [r for r in self.calls.get((server, tool), ()) if rnd - window < r <= rnd]
            if len(prior) >= maximum:
                return None, 'tool rate window exhausted'
        call = ToolCall(server=server, tool=tool, args=args, fields=fields,
                        headers=headers, lease_id=cmd.lease_id, call_index=cmd.call_index)
        self.spent += price
        self.estimated_costs[(cmd.call_index, server, tool)] = price
        self.calls.setdefault((server, tool), []).append(rnd)
        if token_id:
            self.tokens.add(token_id)
        if write_key:
            self.write_keys.add(write_key)
            self.write_operations.add(operation)
            self.provenance.pop(anchor, None)
        return call, None
