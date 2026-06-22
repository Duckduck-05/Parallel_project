\----

Viết báo cáo từ 10-20 trang, tối đa 20 trang:

&#x20; - Song song cấp độ nào: tác vụ hay dữ liệu

&#x20; - Sử dụng kỹ thuật phân rã nào? (data, exploratory, recursive, speculative, hybrid?)

&#x20; - Cách thức song song hóa như thế nào:

&#x20;     +, Phân bổ cho các tiến trình/bộ xử lý như thế nào (Mapping technique (processor/process assignment): 1D, 2D n/sqrt(p) \* n/sqrt(p) block?)

&#x20;     +, Mô tả cách thực hiện giao tiếp (Communication Strategy and Topology? blocking or non-blocking? master-slave? topology: tree? ring? tubecube?...)

&#x20;     +, Có áp dụng kỹ thuật cân bằng tải không (Load Balancing Considerations)?

&#x20;     +, Mã giả thuật toán song song (Pseudo code of Parrallel Algorithm)

&#x20; - Results:

&#x20;     +, Kiểm tra xem kết quả của chương trình song song có chính xác là lời giải của bài toàn nêu ra không?

&#x20;     +, Xác định kích thước dữ liệu đầu vào của bài toán: Chọn số lượng tiến trình bằng số lượng nhân của CPU, ví dụ 3 máy mỗi máy 4 nhân thì chọn tổng số tiến trình là 12, vẽ biểu đồ thời gian chạy trong 2 trường hợp (có và không có thời gian truyền thông) với hai trục: 1 trục là thời gian chạy của chương trình (từ lúc bắt đầu đến lúc kết thúc toàn bộ chương trình), 1 trục là kích thước dữ liệu đầu vào của bài toán => xác định kích thước dữ liệu (gọi là N) của bài toán sao cho thời gian chạy của chương trình khoảng từ 2-3 phút.

&#x20;     +, Kiểm tra tính mịn granularity (kích thước dữ liệu trên mỗi tác vụ nếu song song hóa dựa trên tác vụ hoặc là kích thước dữ liệu trên mỗi tiến trình nếu song song hóa dựa trên dữ liệu): chọn kích thước dữ liệu đầu vào cho toàn bộ chương trình là N, chọn số lượng tiến trình bằng số lượng nhân của CPU, ví dụ 3 máy mỗi máy 4 nhân thì chọn tổng số tiến trình là 12, vẽ biểu đồ thời gian chạy của từng tiến trình tính cả thời gian truyền thông (một cột là một tiến trình, thời gian tính toán và thời gian truyền thông được vẽ chung cột nhưng có màu khác nhau) => xác định xem hệ thống có cân bằng tải không? Nếu không (thời gian rảnh của 2 tiến trình bất kì lệch quá 25%) thì chỉnh lại độ mịn (mịn-fine hơn hoặc thô-coarse hơn).

&#x20;     +, Kiểm tra độ tăng tốc: chọn kích thước dữ liệu đầu vào là 2\*N, biến đổi số lượng tiến trình từ 1, 2, 4, 8,..., 2X với X là tổng số tiến trình ứng với số nhân vật lý của các cpu. Vẽ biểu đồ thời gian chạy trong 2 trường hợp (có và không có thời gian truyền thông) kèm theo biểu đồ độ tăng tốc tương ứng.

