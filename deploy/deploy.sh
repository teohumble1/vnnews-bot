#!/usr/bin/env bash
# Chạy TRÊN LAPTOP. Copy app lên EC2 rồi bootstrap.
#
#   ./deploy/deploy.sh ec2-user@<IP-hoac-DNS> ~/duong-dan-key.pem
#
# Lần đầu: nhớ đã tạo /etc/vnnews-bot.env trên server (script sẽ nhắc nếu thiếu).
set -euo pipefail

HOST="${1:?Thiếu host, vd: ec2-user@1.2.3.4}"
KEY="${2:-}"
SSH_OPTS=(-o StrictHostKeyChecking=accept-new)
[ -n "$KEY" ] && SSH_OPTS+=(-i "$KEY")

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "[1/4] Đẩy source lên $HOST:/tmp/vnnews-bot ..."
if command -v rsync >/dev/null; then
  rsync -az -e "ssh ${SSH_OPTS[*]}" \
    --exclude '__pycache__' --exclude '*.pyc' --exclude '.git' \
    --exclude 'deploy/vnnews-bot.env' \
    "$ROOT"/ "$HOST":/tmp/vnnews-bot/
else
  tar -C "$ROOT" --exclude '__pycache__' --exclude '*.pyc' --exclude '.git' -czf - . \
    | ssh "${SSH_OPTS[@]}" "$HOST" 'rm -rf /tmp/vnnews-bot && mkdir -p /tmp/vnnews-bot && tar -C /tmp/vnnews-bot -xzf -'
fi

echo "[2/4] Chuyển vào /opt/vnnews-bot ..."
ssh "${SSH_OPTS[@]}" "$HOST" 'sudo rm -rf /opt/vnnews-bot && sudo mv /tmp/vnnews-bot /opt/vnnews-bot'

echo "[3/4] Nhắc env (nếu chưa có) ..."
ssh "${SSH_OPTS[@]}" "$HOST" 'test -f /etc/vnnews-bot.env || { echo "  >> Chưa có /etc/vnnews-bot.env. Tạo bằng:"; echo "     sudo cp /opt/vnnews-bot/deploy/vnnews-bot.env.example /etc/vnnews-bot.env && sudo nano /etc/vnnews-bot.env"; exit 1; }'

echo "[4/4] Bootstrap + (re)start service ..."
ssh "${SSH_OPTS[@]}" "$HOST" 'sudo bash /opt/vnnews-bot/deploy/bootstrap.sh'

echo "Hoàn tất. Log:  ssh $HOST 'journalctl -u vnnews-bot -f'"
