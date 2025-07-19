#!/bin/bash
# ������ ��� ���������� ���� � ����������� ����
# �����������: sudo ./update_bot.sh

set -e

REPO_DIR="/path/to/GPTTG"  # ������� ���� � ������ �������
SERVICE_NAME="gpttg-bot"

cd "$REPO_DIR"
echo "���������� ���� �� git..."
git pull

if [ -f "pyproject.toml" ]; then
    echo "���������� ������������ ����� poetry..."
    poetry install
fi

echo "���������� ������� $SERVICE_NAME..."
sudo systemctl restart $SERVICE_NAME

echo "������ �������:"
systemctl status $SERVICE_NAME --no-pager
