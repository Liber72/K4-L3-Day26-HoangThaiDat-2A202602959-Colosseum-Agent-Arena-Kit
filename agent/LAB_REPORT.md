# Báo cáo lab COLOSSEUM — Day 26

Học viên/đội: **HoangThaiDat-2A202602959**. Ngày thực hiện: **14/10/2026**.
Tên đội được lấy từ tên thư mục dự án. Đã đọc các Markdown trong repository
và hoàn thiện đủ Attack, Defend, Prosecute theo `RULES.md`.

## Sản phẩm

| Phần | Kết quả |
|---|---|
| Defend | Gateway thực thi route/admission/authority/budget; guardrails kiểm tra answer; prompt bốn lượt |
| Attack | Deck cá nhân 14 lá, đủ 9 class; lineup 10 lá không lặp với một blank kiểm tra calibration |
| Prosecute | Detector đủ 17 rubric classes, tối đa 4 claim và 1/family; evidence có thể resolve |
| Nộp bài | `submissions/HoangThaiDat-2A202602959.bundle`, tạo bằng `kit.submit` |

Các sửa đổi tính điểm nằm trong `agent/`, `deck/`, `eval/`. Không sửa
`kit/`, `bots/`, `fixtures/`. Code nộp bài chỉ dùng standard library và
API có sẵn của kit; không gọi model endpoint, không cần API key.

## Kiểm chứng

- Corpus thật `df8c55dabb35`: cả 6 checksum trong export manifest khớp;
  không có `truth.json` trong student world.
- G-KEY gate: PASS, không phát hiện vi phạm.
- Deck validator với corpus thật: **0 FAIL, 1 WARN**. Warning còn lại là
  lethality band phải xác nhận bằng engine giải của giảng viên.
- Public suite + 33 test bổ sung: **4.641 passed, 7 skipped, 1 deselected**;
  26 subtests cũng đạt. Kiểm thử bổ sung bao gồm signed token/card/skill,
  wrong act/aud, expiry/replay, lease, exactly-once, partial, privacy,
  real action parser, history và gọi server/A2A thật trên fixture sạch.
- Một test bị loại: `test_run_probe_vectors_unsandboxed_baseline`.
  Khi chạy toàn bộ public suite trên Windows, test trong kit này gọi
  POSIX `libc.open` qua ctypes và lỗi `AttributeError: function 'open' not
  found`. Kết quả lần chạy đầy đủ: 4.608 passed, 7 skipped, 1 failed.
  Không sửa hoặc đánh dấu skip trong code kit/test để che lỗi nền tảng.
- Đã chạy lại nguyên target `make test` trong **WSL Ubuntu 24.04**, với
  Python 3.12.3 và pytest 9.1.1 trong venv Linux riêng. Kết quả:
  **4.609 passed, 7 skipped, 0 failed**, exit code 0; không dùng `-k` để
  loại test. `test_run_probe_vectors_unsandboxed_baseline` đã pass trên
  Linux nhờ có `libc.open` và `/bin/cat`. Ba test sandbox macOS và bốn
  test cần nguồn/repo giảng viên vẫn được kit tự skip. Log đầy đủ:
  `.lab-artifacts/make-test-wsl.txt`.
- Công tố: **34/34 defects** trên 40 fixture, precision=recall=F1=1.000;
  false_claim_rate=0; không unproven/rejected/errors/timeouts. Đủ 17 class,
  và 6 trace sạch không có claim. Renumber toàn bộ event vẫn chứng minh
  đủ 34 lỗi, tránh phụ thuộc vị trí fixture cố định.

## Spar luyện tập

Chạy `--as all --rounds 10 --seed 1 --ui`; spar dừng sớm khi KO.

| Bot | HP đội | HP bot | Kết quả |
|---|---:|---:|---|
| rookie | 100 | 0 | Thắng, KO vòng 6 |
| operator | 100 | 0 | Thắng, KO vòng 6 |
| adversary | 72 | 0 | Thắng, KO vòng 9 |

Replay và summary nằm tại `runs/spar-rookie-1/`,
`runs/spar-operator-1/`, `runs/spar-adversary-1/`. Một số protocol_misuse
vẫn hiện trong MISSED vì đã chọn enforcement_failure có trọng số cao hơn
cùng family A; không thể nộp thêm một claim family A trong cùng exchange.

Giới hạn: spar hiện dùng tool plan và câu trả lời được script sẵn; nó
không chạy đầy đủ reasoning của `agent/prompt.md`, không tự gọi
`Gateway.prepare_answer` và không chứng minh khả năng tổng quát trong
tournament. Budget trong spar cũng được tạo lại từng exchange. Test bổ
sung đã kiểm tra reservation mười vòng, token hợp lệ và luồng server thật
riêng khỏi các giới hạn đó. Tám lớp semantic cần referee/model của giải;
điểm fixture 100% không phải cam kết đúng trên mọi trace.

## Chạy lại trên Windows

```powershell
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe .lab-artifacts/test_solution.py
.\.venv\Scripts\python.exe -m pytest tests/ .lab-artifacts/test_solution.py -q --tb=short -k "not test_run_probe_vectors_unsandboxed_baseline"
.\.venv\Scripts\python.exe -m kit.gate_no_key
.\.venv\Scripts\python.exe -m eval.prosecute
.\.venv\Scripts\python.exe validate_deck.py deck/deck.json deck/lineup.json --world kit/world/df8c55dabb35
.\.venv\Scripts\python.exe spar.py --bot adversary --as all --rounds 10 --seed 1 --ui
.\.venv\Scripts\python.exe -m kit.submit --team HoangThaiDat-2A202602959
.\.venv\Scripts\python.exe .lab-artifacts/verify_submission.py
```

Chạy pytest trong môi trường cho phép tạo thư mục tạm Windows. Kết quả
kiểm tra và fingerprint bundle được lưu trong `.lab-artifacts/`.
Bundle đã đóng gói cục bộ; việc gửi lên hệ thống lớp/giải vẫn do học viên
thực hiện qua kênh nộp bài của giảng viên.

## Chạy nguyên make test bằng WSL từ PowerShell

Môi trường Linux đã cài tại `/root/.venvs/colosseum-py312`, tách khỏi
`.venv` Windows. Từ thư mục gốc dự án trong PowerShell:

```powershell
wsl -d Ubuntu-24.04 --exec make test BIN=/root/.venvs/colosseum-py312/bin
```

`BIN` chỉ chọn interpreter Linux cho Makefile; không thay đổi bộ test
hay nội dung kit. Venv Linux dùng pytest 9.1.1; WSL đã có `make` và
`python3.12-venv` để có thể chạy lại.
