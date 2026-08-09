#!/usr/bin/env bash
# Chạy TRÊN server EC2 với quyền root (sudo). Cài user + systemd service.
# Giả định: source app đã nằm ở /opt/vnnews-bot và /etc/vnnews-bot.env đã tồn tại.
set -euo pipefail

APP_DIR=/opt/vnnews-bot
ENV_FILE=/etc/vnnews-bot.env
UNIT=/etc/systemd/system/vnnews-bot.service

echo "[1/5] Kiểm tra python3..."
command -v python3 >/dev/null || {
  echo "  cài python3..."
  (command -v dnf >/dev/null && dnf install -y python3) \
    || (command -v yum >/dev/null && yum install -y python3) \
    || (command -v apt-get >/dev/null && apt-get update && apt-get install -y python3)
}
python3 --version

echo "[2/5] Tạo user hệ thống 'vnnews'..."
id vnnews >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin vnnews

echo "[3/5] Kiểm tra source & env..."
test -d "$APP_DIR/vnnews_bot" || { echo "  THIẾU $APP_DIR/vnnews_bot — copy source trước."; exit 1; }
test -f "$ENV_FILE" || { echo "  THIẾU $ENV_FILE — tạo từ vnnews-bot.env.example."; exit 1; }
chown -R root:root "$APP_DIR"
chmod 600 "$ENV_FILE"; chown root:root "$ENV_FILE"

echo "[4/5] Cài systemd unit..."
install -m 644 "$APP_DIR/deploy/vnnews-bot.service" "$UNIT"
systemctl daemon-reload
systemctl enable vnnews-bot

echo "[5/5] Khởi động..."
systemctl restart vnnews-bot
sleep 2
systemctl --no-pager --full status vnnews-bot | head -12 || true
echo
echo "Xong. Xem log:  journalctl -u vnnews-bot -f"
