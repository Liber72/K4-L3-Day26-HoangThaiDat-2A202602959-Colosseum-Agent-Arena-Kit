# Bộ bài — HoangThaiDat-2A202602959

14 lá: 10 attack + 4 blank; cân bằng 4 MCP, 4 A2A, 2 gateway và đủ 9
duel classes. Tất cả attack dùng `defense_event="gateway.denied"` theo
hướng dẫn định dạng trong kit. Op/value/target dùng vocabulary của kit.

| Lá | Class | Mục tiêu và ASK |
|---|---|---|
| atk_01 | shadow | Concept baggage; slides trả nội dung từ decoy day7 |
| atk_02 | replica_flip | Concept stategraph; đổi replica envelope trên path e0614beb có drift |
| atk_03 | drift | `current_version_of` của day18, path d8f95a7b; đổi content replica |
| atk_04 | poisoned_result | `source_of` của Claim:claim-032daacb/c/001; chèn Note vào research |
| atk_05 | schema_bomb | Định nghĩa mcp registry; inflate catalog bằng 40 decoy rows |
| atk_06 | header_spoof | record_mastery cho sv-0417; bỏ If-Match và Idempotency-Key |
| atk_07 | identity | Peer curriculum-analyst phục vụ sai act sv-0392 |
| atk_08 | forged_card | Card citation-checker có skill thêm nhưng chữ ký cũ |
| atk_09 | faithless_peer | Peer trả sai course_day cho Concept action |
| atk_10 | identity | Token của roster có audience curriculum-analyst |
| blk_01–04 | blank | Định nghĩa traceparent, inputschema, backlinks và nguồn Claim trên stack sạch |

Hai thay đổi có chủ đích từ starter:

- `atk_03` chọn day18: dữ liệu thật có 45 content frames working và 31
  canonical, delta 14. Người phòng thủ cần giải quyết replica thay vì coi
  số frame/idx của hai bản là tương đương.
- `atk_04` hỏi nguồn Claim để khiến research trở thành đường tìm nguồn
  tự nhiên, thay cho một định nghĩa có thể lấy thẳng từ glossary. Nó vẫn
  dùng Note có thật trong corpus, không tạo anchor mới.

Lineup khóa 10 lá không lặp: atk_04, blk_01, atk_05, atk_03, atk_01,
atk_08, atk_06, atk_02, atk_09, atk_07. Blank ở đầu giúp thử calibration;
các lỗi route/peer/act xuất hiện ở cuối khi round scale cao hơn.

```powershell
.\.venv\Scripts\python.exe validate_deck.py deck/deck.json deck/lineup.json --world kit/world/df8c55dabb35
```

Validator phải dùng corpus thật, không dùng fixture cho anchor thật.
Lethality band của giải cần engine riêng của giảng viên; validator báo
warning về giới hạn đó. Spar cục bộ là bằng chứng luyện tập, không thay
thế chứng nhận lethality band trong tournament.
