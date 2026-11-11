#!/bin/zsh
# 터치 DJ: 더블클릭하면 이 USB의 묶음(dj로 시작하는 파일)을 지금 업데이트해요.
# 렉박에서 새 곡을 넣거나 플레이리스트·큐를 바꿔 내보낸 뒤에 실행하세요.
cd "${0:A:h}" || exit 1
USB="$PWD"
TOOLS="$USB/.touchdj"
clear
echo "터치 DJ 묶음 업데이트 · ${USB:t}"
echo "끝날 때까지 USB를 빼지 마세요."
echo

PY=""
for p in /usr/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  if [[ -x "$p" ]] && "$p" -c 'import tarfile, fcntl' >/dev/null 2>&1; then PY="$p"; break; fi
done
if [[ -z "$PY" ]]; then
  echo "파이썬이 필요해요. '개발자 도구 설치' 창이 뜨면 '설치'를 누르고, 끝나면 이 파일을 다시 더블클릭해 주세요."
  xcode-select --install >/dev/null 2>&1
  exit 1
fi
if [[ ! -f "$TOOLS/touchdj_auto.py" ]]; then
  echo "USB 안의 .touchdj 폴더가 없어요. 이 파일은 렉박 USB 맨 위에 있어야 해요."
  exit 1
fi

"$PY" "$TOOLS/touchdj_auto.py" --now "$USB"
rc=$?
echo
if (( rc == 0 )); then
  echo "✓ 끝났어요. 이제 USB를 빼도 돼요. 이 창은 닫아도 돼요."
else
  echo "✗ 업데이트하지 못했어요. 위 내용을 캡처해서 Claude에게 보여 주세요."
fi
