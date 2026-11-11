#!/bin/zsh
# 터치 DJ: 더블클릭 한 번이면, 이후로는 렉박에서 USB로 내보낼 때마다 Mac이 알아서 묶음을 업데이트해요.
# 끄려면 같은 폴더의 '터치DJ 자동 업데이트 끄기.command'를 더블클릭하세요.
cd "${0:A:h}" || exit 1
clear
echo "터치 DJ 자동 업데이트 켜기"
echo
TOUCHDJ_SRC="$PWD/.touchdj" zsh "$PWD/.touchdj/install-mac.sh"
echo
echo "이 창은 닫아도 돼요."
