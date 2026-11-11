#!/bin/zsh
# Touch DJ: install the automatic USB bundle update on a Mac (run once).
#   curl -fsSL https://raw.githubusercontent.com/y2kjang-sudo/Touch-DJ/main/tools/install-mac.sh | zsh
# Remove again:
#   curl -fsSL https://raw.githubusercontent.com/y2kjang-sudo/Touch-DJ/main/tools/install-mac.sh | zsh -s -- --remove
set -u
SRC="https://raw.githubusercontent.com/y2kjang-sudo/Touch-DJ/main/tools"
APP="$HOME/Library/Application Support/TouchDJ"
LABEL="com.touchdj.autobundle"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
GUI="gui/$(id -u)"

if [[ "${1:-}" == "--remove" ]]; then
  launchctl bootout "$GUI/$LABEL" 2>/dev/null
  rm -f "$PLIST"; rm -rf "$APP"
  echo "터치 DJ 자동 업데이트를 지웠어요."; exit 0
fi

PY=""
for p in /usr/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  if [[ -x "$p" ]] && "$p" -c 'import tarfile, fcntl' >/dev/null 2>&1; then PY="$p"; break; fi
done
if [[ -z "$PY" ]]; then
  echo "파이썬이 필요해요. 화면에 '개발자 도구 설치' 창이 뜨면 '설치'를 누르고, 끝나면 이 명령을 한 번 더 붙여 넣어 주세요."
  xcode-select --install >/dev/null 2>&1; exit 1
fi

mkdir -p "$APP" "$HOME/Library/LaunchAgents"
for f in make_bundles.py touchdj_auto.py; do
  if [[ -n "${TOUCHDJ_SRC:-}" ]]; then cp "$TOUCHDJ_SRC/$f" "$APP/$f.new" || exit 1      # from the USB (double-click file)
  elif ! curl -fsSL "$SRC/$f" -o "$APP/$f.new"; then echo "내려받기 실패: $f (인터넷 연결을 확인해 주세요)"; exit 1; fi
  mv "$APP/$f.new" "$APP/$f"
done

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>$PY</string><string>$APP/touchdj_auto.py</string></array>
  <key>StartInterval</key><integer>30</integer>
  <key>StartOnMount</key><true/>
  <key>RunAtLoad</key><true/>
  <key>ProcessType</key><string>Background</string>
  <key>LowPriorityIO</key><true/>
  <key>StandardOutPath</key><string>$APP/agent.out</string>
  <key>StandardErrorPath</key><string>$APP/agent.out</string>
</dict></plist>
EOF
launchctl bootout "$GUI/$LABEL" 2>/dev/null
launchctl bootstrap "$GUI" "$PLIST" || { echo "자동 실행 등록에 실패했어요."; exit 1; }
echo "자동 업데이트를 켰어요. 렉박에서 USB로 내보내면 1분쯤 뒤 알아서 묶음을 업데이트하고 알림을 띄워요."

# USBs that are plugged in right now: update them here once (this also lets macOS ask for USB access)
for v in /Volumes/*(N); do
  [[ -f "$v/PIONEER/rekordbox/export.pdb" ]] || continue
  name="${v:t}"
  if [[ ! -f "$v/dj1_rekordbox.tar" ]]; then
    printf "'%s'에는 아직 터치 DJ 묶음이 없어요. 지금 만들까요? 이후로는 자동으로 업데이트돼요. (y/n) " "$name"
    read -r ans </dev/tty; [[ "$ans" == [yY]* ]] || continue
  fi
  echo "'$name' 업데이트 중… 끝날 때까지 USB를 빼지 마세요."
  "$PY" "$APP/touchdj_auto.py" --now "$v"
done
echo "macOS가 'python3이(가) 이동식 볼륨의 파일에 접근하려고 합니다'라고 물으면 '허용'을 눌러 주세요."
