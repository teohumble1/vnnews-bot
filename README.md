# vnnews-bot

Bot Telegram đẩy **tin tức real-time báo Việt Nam**. Quét RSS các báo lớn theo chu kỳ,
lọc bài mới (chống trùng) rồi gửi vào chat/channel Telegram của bạn.

- **Stdlib-only** — không cần `pip install` gì. Chỉ cần Python 3.10+.
- Nguồn mặc định: VnExpress, Tuổi Trẻ, Thanh Niên, Dân Trí, VietnamNet, Người Lao Động, Tiền Phong.
- Tự xử lý gzip, Atom fallback, strip HTML, chống trùng lưu ra đĩa.

## 1. Tạo bot & lấy token

1. Mở Telegram, chat với **@BotFather** → `/newbot` → đặt tên → nhận **token** dạng `123456:ABC...`.
2. Lấy **chat_id** nơi muốn nhận tin:
   - Gửi 1 tin vào group/channel, rồi mở:
     `https://api.telegram.org/bot<TOKEN>/getUpdates` → tìm `"chat":{"id":...}`.
   - Channel có id âm dạng `-100...`. Nhớ **add bot làm admin** của channel.

## 2. Cấu hình

Cách A — biến môi trường (nhanh nhất):

```bash
export VNNEWS_BOT_TOKEN="123456:ABC..."
export VNNEWS_CHAT_ID="-1001234567890"
```

Cách B — file config: copy `config.example.json` tới
`~/.config/vnnews-bot/config.json` và điền token/chat_id. (Env sẽ override file.)

## 3. Chạy

```bash
cd ~/vnnews-bot

python3 -m vnnews_bot sources     # thử tải từng nguồn RSS
python3 -m vnnews_bot check       # kiểm tra token + gửi 1 tin thử
python3 -m vnnews_bot dry-run     # quét & in bài mới, KHÔNG gửi
python3 -m vnnews_bot once        # quét & gửi đúng 1 vòng
python3 -m vnnews_bot run         # chạy liên tục (mỗi poll_interval giây)
```

> Lần chạy đầu sẽ có **rất nhiều** bài "mới" (toàn bộ feed). `max_per_cycle` (mặc định 8)
> giới hạn số bài gửi mỗi vòng, phần còn lại được đánh dấu đã-thấy để không dồn spam về sau.
> Muốn "seed" im lặng lần đầu: chạy `dry-run` một lần trước, hoặc để nó tự trải qua vài vòng.

## 4. Chạy nền bằng systemd (tùy chọn)

`~/.config/systemd/user/vnnews-bot.service`:

```ini
[Unit]
Description=vnnews-bot Telegram
After=network-online.target

[Service]
Environment=VNNEWS_BOT_TOKEN=123456:ABC...
Environment=VNNEWS_CHAT_ID=-1001234567890
ExecStart=/usr/bin/python3 -m vnnews_bot run
WorkingDirectory=%h/vnnews-bot
Restart=on-failure

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now vnnews-bot
journalctl --user -u vnnews-bot -f
```

## 5. Deploy AWS EC2 (chạy 24/7, độc lập laptop)

Bot chỉ gọi ra ngoài (RSS + Telegram), **không cần mở cổng inbound** nào ngoài SSH.

**a) Tạo instance** (AWS Console → EC2 → Launch instance):
- AMI: **Amazon Linux 2023** (hoặc Ubuntu) · Type: **t3.micro** (free tier)
- Key pair: tạo/chọn `.pem` để SSH
- Security group: chỉ cần **inbound SSH (22)** từ IP của bạn. Outbound để mặc định (all).

**b) Từ laptop, deploy 1 lệnh:**

```bash
cd ~/vnnews-bot
./deploy/deploy.sh ec2-user@<IP-hoặc-DNS> ~/duong-dan-key.pem
```

Lần đầu script sẽ dừng và nhắc tạo file env trên server. SSH vào và tạo:

```bash
ssh -i ~/key.pem ec2-user@<IP>
sudo cp /opt/vnnews-bot/deploy/vnnews-bot.env.example /etc/vnnews-bot.env
sudo nano /etc/vnnews-bot.env      # điền VNNEWS_BOT_TOKEN + VNNEWS_CHAT_ID
```

Rồi chạy lại `./deploy/deploy.sh ...` — nó sẽ cài service và start.

**c) Kiểm tra / vận hành trên server:**

```bash
sudo systemctl status vnnews-bot
journalctl -u vnnews-bot -f          # xem log realtime
sudo systemctl restart vnnews-bot
sudo systemctl stop vnnews-bot
```

Chạy dưới user hệ thống `vnnews`, tự restart khi lỗi, tự bật lại sau reboot instance.
State (link đã gửi) lưu ở `/var/lib/vnnews-bot/seen.json`. Token nằm ở `/etc/vnnews-bot.env`
(chmod 600, chỉ root đọc). Cập nhật code sau này: chỉ cần chạy lại `deploy.sh`.

## Cấu trúc

```
vnnews_bot/
  config.py     # nguồn RSS + đọc token/chat (env > file)
  feeds.py      # tải & parse RSS/Atom, giải nén gzip, strip HTML
  telegram.py   # client Bot API (sendMessage/getMe)
  store.py      # chống trùng, lưu link đã gửi (FIFO)
  bot.py        # vòng lặp quét → lọc → gửi
  __main__.py   # CLI
tests/          # test offline, python3 -m unittest
```

## Tùy chỉnh nguồn

Sửa `sources` trong `config.json` (map `"Tên": "URL RSS"`), hoặc chỉnh
`DEFAULT_SOURCES` trong `vnnews_bot/config.py`. Muốn tin theo chủ đề? Dùng RSS chuyên mục,
vd `https://vnexpress.net/rss/the-thao.rss`, `.../thoi-su.rss`, `.../kinh-doanh.rss`.
