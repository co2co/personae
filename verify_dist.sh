#!/usr/bin/env bash
# 纯引擎分发端到端验证：解压到空目录 -> 起服务 -> 探活
set -u
ZIP="D:/codes/my-st/my-st-v0.4.3.zip"
DIST="D:/codes/_dist_test"
RUNID="run-$(date +%s)"
TARGET="$DIST/$RUNID"
PORT=5051
SRC_VENV="D:/codes/my-st/engine/venv"
RESULT="$DIST/verify.result"

mkdir -p "$DIST"

echo "=== [1] 解压到全新唯一目录 ==="
mkdir -p "$TARGET"
unzip -o -q "$ZIP" -d "$TARGET"
echo "解压完成，顶层内容："
ls -1 "$TARGET"

echo
echo "=== [2] 结构断言（解压后、注入 venv 前）==="
fail=0
assert() { if [ "$1" = "1" ]; then echo "  [PASS] $2"; else echo "  [FAIL] $2"; fail=1; fi; }

top=$(ls -1 "$TARGET" | wc -l)
assert "$([ "$top" = "1" ] && echo 1 || echo 0)" "顶层仅一个 engine/ 目录（实际 $top 项）"
assert "$([ -d "$TARGET/engine" ] && echo 1 || echo 0)" "存在 engine/"

assert "$([ ! -e "$TARGET/tests" ] && echo 1 || echo 0)" "不含 tests/"
assert "$([ ! -d "$TARGET/engine/venv" ] && echo 1 || echo 0)" "不含 venv/（zip 不携带 venv）"
assert "$([ ! -d "$TARGET/engine/data/sessions" ] && echo 1 || echo 0)" "不含 engine/data/sessions/"
assert "$([ ! -e "$TARGET/engine/data/state.json" ] && echo 1 || echo 0)" "不含 engine/data/state.json"

for f in engine/app.py engine/run.bat engine/install.bat engine/requirements.txt engine/static/index.html engine/data/config.json engine/data/characters engine/data/worlds; do
  assert "$([ -e "$TARGET/$f" ] && echo 1 || echo 0)" "含 $f"
done

echo
echo "=== [3] 注入 venv（python -m venv + .pth 指向项目 site-packages，模拟 install.bat；离线、零复制）==="
if [ -d "$SRC_VENV" ]; then
  "$SRC_VENV/Scripts/python.exe" -m venv "$TARGET/engine/venv" >/dev/null 2>&1
  printf '%s\n' "$SRC_VENV/Lib/site-packages" > "$TARGET/engine/venv/Lib/site-packages/zz_project.pth"
  assert "$([ -e "$TARGET/engine/venv/Scripts/python.exe" ] && echo 1 || echo 0)" "venv 已就位（venv/Scripts/python.exe）"
  "$TARGET/engine/venv/Scripts/python.exe" -c "import flask" 2>/dev/null && echo "  [info] flask 可导入（经 .pth）" || echo "  [warn] flask 导入失败"
else
  echo "  [SKIP] 源 venv 不存在：$SRC_VENV"
fi

echo
echo "=== [4] 运行解压后的 engine/run.bat（自定位启动，端口 $PORT）==="
"$TARGET/engine/venv/Scripts/python.exe" -c "print('venv python 可用')"
( cmd //c "$TARGET/engine/run.bat" > "$DIST/$RUNID.run.bat.out" 2>&1 ) &
RUNPID=$!
echo "run.bat 已后台启动（外壳 PID=$RUNPID），等待服务就绪..."

ready=0
for i in $(seq 1 40); do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$PORT/" 2>/dev/null)
  if [ "$code" = "200" ]; then ready=1; echo "  服务在第 ${i}s 就绪（HTTP $code）"; break; fi
  sleep 1
done

echo
echo "=== [5] 端点检查 ==="
check() {
  c=$(curl -s -o /dev/null -w "%{http_code}" "$1" 2>/dev/null)
  assert "$([ "$c" = "200" ] && echo 1 || echo 0)" "$2 -> HTTP $c"
}
check "http://127.0.0.1:$PORT/" "首页 /"
check "http://127.0.0.1:$PORT/api/characters" "角色 API /api/characters"
check "http://127.0.0.1:$PORT/docs/worldbook" "世界书文档 /docs/worldbook"

n=$(curl -s "http://127.0.0.1:$PORT/api/characters" 2>/dev/null | python -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null)
echo "  角色数量（API 实查）= ${n:-?}"

echo
echo "=== [6] 关闭服务（按端口 $PORT 精准 kill，不影响开发服务 5000）==="
pid=$(netstat -ano 2>/dev/null | grep ":$PORT " | grep LISTENING | awk '{print $5}' | head -1)
if [ -n "$pid" ]; then taskkill //F //PID "$pid" >/dev/null 2>&1 && echo "  已关闭监听进程 PID=$pid"; else echo "  未找到监听进程"; fi
taskkill //F //PID "$RUNPID" >/dev/null 2>&1
sleep 1

echo
echo "=== [7] 清理临时目录 ==="
rm -rf "$TARGET" 2>/dev/null
echo "  已移除 $TARGET"

echo
echo "=== [8] 总结 ==="
if [ "$ready" = "1" ] && [ "$fail" = "0" ]; then
  echo "RESULT: PASS —— 纯引擎分发端到端验证通过"
  echo "PASS" > "$RESULT"
else
  echo "RESULT: FAIL —— 见上方 [FAIL] 项（ready=$ready, struct_fail=$fail）"
  echo "FAIL" > "$RESULT"
fi
echo "详细日志见 $DIST/$RUNID.run.bat.out 与本次输出"
