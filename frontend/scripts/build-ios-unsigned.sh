#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

if ! xcodebuild -version >/dev/null 2>&1; then
  echo "未找到完整 Xcode，无法编译 iOS App。"
  echo "当前仅安装了 Command Line Tools，请先："
  echo "  1. 从 App Store 安装 Xcode（约 10+ GB）"
  echo "  2. sudo xcode-select -s /Applications/Xcode.app/Contents/Developer"
  echo "  3. xcodebuild -version 确认输出 Xcode 版本"
  exit 1
fi

npx cap telemetry off >/dev/null 2>&1 || true
pnpm build
npx cap sync ios

ARCHIVE_DIR="$ROOT_DIR/ios-build"
rm -rf "$ARCHIVE_DIR"
mkdir -p "$ARCHIVE_DIR"

xcodebuild \
  -project ios/App/App.xcodeproj \
  -scheme App \
  -configuration Release \
  -sdk iphoneos \
  -derivedDataPath "$ARCHIVE_DIR/DerivedData" \
  CODE_SIGNING_ALLOWED=NO \
  CODE_SIGNING_REQUIRED=NO \
  CODE_SIGN_IDENTITY="" \
  build

APP_PATH="$ARCHIVE_DIR/DerivedData/Build/Products/Release-iphoneos/App.app"
if [ ! -d "$APP_PATH" ]; then
  echo "App.app was not produced; check the xcodebuild output above." >&2
  exit 1
fi

rm -rf "$ARCHIVE_DIR/Payload"
mkdir -p "$ARCHIVE_DIR/Payload"
cp -R "$APP_PATH" "$ARCHIVE_DIR/Payload/App.app"
(cd "$ARCHIVE_DIR" && zip -qry 115-resource-manager-unsigned.ipa Payload)
echo "Created $ARCHIVE_DIR/115-resource-manager-unsigned.ipa"
