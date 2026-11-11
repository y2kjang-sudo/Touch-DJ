#!/bin/zsh
# 터치 DJ: 자동 업데이트를 끄고 Mac에 설치한 파일을 지워요. USB의 묶음은 그대로 둬요.
cd "${0:A:h}" || exit 1
clear
zsh "$PWD/.touchdj/install-mac.sh" --remove
echo "이 창은 닫아도 돼요."
