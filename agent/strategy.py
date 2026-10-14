"""Pure routing, masks, delegation and credit planning for a ten-round duel.

Prices come from the kit's current table: a query with one body, a frame
read and provenance cost 9 credits together. Catalog dumps cost 12 and 10.
The gateway uses round_allowance so credits remain available for late rounds.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from kit.mcp.specs import TOOL_SPECS, cost

ROUNDS_PER_DUEL = 10
SAFE_STARTING_RESERVE = 0.5
CATALOG_TRAP_TOOLS = frozenset({('registry', 'list_servers'), ('glossary', 'list_terms')})
DEPRECATED_SUCCESSORS = {('slides', 'search'): ('slides', 'query')}


def disciplined_round_cost() -> int:
    return (cost('slides', 'query', fields=('body', 'title'), n_rows=1)
            + cost('slides', 'get_frame') + cost('registry', 'provenance'))


def careless_round_cost() -> int:
    return (cost('registry', 'list_servers', fields=('*',))
            + cost('glossary', 'list_terms')
            + 3 * cost('slides', 'get_frame', fields=('*',)))


def is_catalog_trap(server: str, tool: str, fields: tuple[str, ...] = ()) -> bool:
    return (server, tool) in CATALOG_TRAP_TOOLS and fields in ((), ('*',))


def cheap_mask(server: str, tool: str, needed: tuple[str, ...]) -> tuple[str, ...]:
    mask = tuple(sorted(set(needed)))
    spec = TOOL_SPECS[(server, tool)]
    if set(mask) - set(spec.all_fields):
        raise ValueError('requested mask contains unsupported fields')
    return mask


def successor_of(server: str, tool: str) -> tuple[str, str] | None:
    return DEPRECATED_SUCCESSORS.get((server, tool))


def round_allowance(round_no: int, credits_left: int, spent_this_round: int = 0) -> int:
    """Reserve six credits per future round; stay below the referee's 11.

    Targets 8/10/11 in early/middle/late rounds total 97 credits. The live
    context is authoritative, including costs of failed calls and penalties.
    """
    round_no = min(ROUNDS_PER_DUEL, max(1, round_no))
    target = 8 if round_no <= 3 else 10 if round_no <= 7 else 11
    reserve = 6 * (ROUNDS_PER_DUEL - round_no)
    return max(0, min(target, credits_left + spent_this_round - reserve))


@dataclass
class BudgetPacer:
    starting_pool: int = 100
    rounds_total: int = ROUNDS_PER_DUEL
    _spent: int = field(default=0, init=False)
    _spent_by_round: dict[int, int] = field(default_factory=dict, init=False)

    def record_spend(self, round_no: int, cost: int) -> None:
        if type(cost) is not int or cost < 0:
            raise ValueError('cost must be a non-negative integer')
        self._spent += cost
        self._spent_by_round[round_no] = self._spent_by_round.get(round_no, 0) + cost

    @property
    def credits_left(self) -> int:
        return self.starting_pool - self._spent

    @property
    def credits_spent(self) -> int:
        return self._spent

    def is_affordable(self, round_no: int, cost: int, *, reserve: float = SAFE_STARTING_RESERVE) -> bool:
        if cost < 0:
            return False
        future_rounds = max(0, self.rounds_total - round_no)
        floor = self.starting_pool * reserve * future_rounds / max(1, self.rounds_total - 1)
        return self.credits_left - cost >= floor

    def bankrupt_by(self) -> int | None:
        running = self.starting_pool
        for round_no, spent in sorted(self._spent_by_round.items()):
            running -= spent
            if running < 0:
                return round_no
        return None


@dataclass(frozen=True, slots=True)
class ReplicaChoice:
    replica: str
    reason: str


def pick_replica(*, path_id: str | None, known_drifting: bool,
                 prefers_fresh: bool = True, fresher: str | None = None) -> ReplicaChoice:
    if known_drifting and prefers_fresh and fresher in ('w', 'c'):
        return ReplicaChoice(fresher, f'{path_id}: freshness established by provenance')
    reason = 'drift unresolved; obtain provenance before citing' if known_drifting else 'no observed drift'
    return ReplicaChoice('w', f'{path_id}: {reason}')


@dataclass
class ResultCache:
    """Cache paid fields, with an optional exchange key for citation safety.

    A cache hit from another round must be revalidated before it is cited.
    A narrower mask may reuse a wider cached row because those fields were paid.
    """
    _store: dict[tuple[str, tuple[str, ...], int | None], Mapping[str, Any]] = field(default_factory=dict)

    def get(self, anchor: str, fields: tuple[str, ...], *, round_no: int | None = None) -> Mapping[str, Any] | None:
        needed = set(fields)
        for (key_anchor, mask, key_round), row in self._store.items():
            if key_anchor == anchor and key_round == round_no and needed <= set(mask):
                return {k: v for k, v in row.items() if k in needed or k == 'anchor'}
        return None

    def put(self, anchor: str, fields: tuple[str, ...], row: Mapping[str, Any],
            *, round_no: int | None = None) -> None:
        self._store[(anchor, tuple(sorted(set(fields))), round_no)] = dict(row)

    def __len__(self) -> int:
        return len(self._store)


def should_delegate(*, own_confidence: float, calls_used_this_window: int,
                    calls_allowed_this_window: int, credits_left: int,
                    delegate_cost: int, min_confidence_to_skip: float = 0.85) -> bool:
    return (own_confidence < min_confidence_to_skip
            and calls_used_this_window < calls_allowed_this_window
            and 0 <= delegate_cost <= credits_left)


if __name__ == '__main__':
    disciplined, careless = disciplined_round_cost(), careless_round_cost()
    assert disciplined == 9 and careless == 49
    print(f'Disciplined round: {disciplined}; careless round: {careless} credits.')
    print(f'Ten disciplined rounds: {10 * disciplined}/100 credits.')
    pool = 100
    for rnd in range(1, 11):
        pool -= round_allowance(rnd, pool)
    assert pool == 3
    print(f'Ten rounds at the gateway allowance leave {pool} credits.')
