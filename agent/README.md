# Phòng thủ — phần đã triển khai

`Gateway.decide` là điểm thực thi duy nhất, synchronous và không I/O.
Nó trả `Decision`; arena thực hiện ToolCall và ghi trace.

| File | Trách nhiệm |
|---|---|
| `gateway.py` | API Command/Decision; gọi policy; nhận observation; kiểm tra câu trả lời |
| `policy.py` | Route theo header; xác thực card/token/skill; quyền theo `ctx.act`; lease, write và budget |
| `strategy.py` | Mask hẹp, successor, cache theo vòng và giữ credit cho cả duel |
| `guardrails.py` | Citation, injection, privacy, arithmetic, partial results và abstention |
| `telemetry.py` | Ghi chú nội bộ qua `ctx.emit`; không phải bằng chứng được chấm |
| `prompt.md` | Kế hoạch bốn lượt và chính sách trả lời, chồng lên prompt của harness |

Admission A2A kiểm tra signature, declared skill, audience, act, expiry,
replay và cú pháp traceparent. Roster dùng skill `role_of`/`who_enrolled`
để gọi wire tool `lookup_learner`. Signed peer vẫn cần cross-check facts.

Write chỉ được gửi với scope đúng, Learner thuộc act và provenance mới.
Policy sinh key xác định và chặn operation đã gửi, kể cả retry thêm key
hoặc argument không ảnh hưởng dữ liệu. Sau một write, provenance bị tiêu
thụ. Provenance và lease quan sát được không được tái dùng ở vòng sau.

`slides.search` được đổi sang `slides.query`, chuyển `snippet` sang `body`
và dùng anchor trong envelope. Query được giới hạn tối đa ba hàng; catalog
mặc định được thu hẹp, còn mask hẹp do caller yêu cầu được giữ nguyên.
Budget tối đa theo vòng là 8/10/11, tổng 97/100 nếu dùng hết các mức này.

Caller tin cậy gọi `note_card`, `note_provenance`, `note_drift`,
`note_result(call, result)` để chuyển observation vào gateway. Policy cũng
đọc các entry mới trong `ctx.history` dạng `{command, decision, outcome}`.
Không lấy etag/card giả trong `cmd.args` làm observation.

Trước khi xuất câu trả lời, caller dùng:

```python
safe_answer = gateway.prepare_answer(proposed_answer, ask)
```

Kết quả chỉ cite dữ liệu của vòng hiện tại; dữ liệu peer phải được MCP
corroborate; partial phải hoàn thành continuation hoặc đọc riêng đầy đủ
frame sẽ cite (không coi toàn bộ danh sách đã đầy đủ). Payload cấu trúc cũng
được kiểm tra/redact, không chỉ `text`. Guardrail trả câu abstain nếu kiểm
tra thất bại. Hàm này không tự can thiệp vào `ANSWER` của harness: caller
cần gọi nó, còn prompt quy định cùng hợp đồng cho model.

Chạy trên Windows từ thư mục gốc:

```powershell
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe .lab-artifacts/test_solution.py
.\.venv\Scripts\python.exe -m agent.gateway
.\.venv\Scripts\python.exe -m agent.strategy
```

Xem [LAB_REPORT.md](LAB_REPORT.md) để biết kết quả và giới hạn kiểm chứng.
