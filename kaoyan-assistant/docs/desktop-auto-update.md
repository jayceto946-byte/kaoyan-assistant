# 桌面版自动更新流程

桌面版使用 `electron-updater` + GitHub Releases。

## 发版流程

1. 修改 `desktop/package.json` 的 `version`，例如从 `0.1.0` 改为 `0.1.1`。
2. 提交代码并推送到 GitHub。
3. 创建并推送 tag：

```powershell
git tag v0.1.1
git push origin v0.1.1
```

4. GitHub Actions 会自动：
   - 安装 Python/Node 依赖
   - 构建前端
   - 用 PyInstaller 构建后端 exe
   - 用 electron-builder 构建 Windows 安装包
   - 发布到 GitHub Releases

5. 用户在桌面软件设置页点击“检查更新”。如果 GitHub Releases 有更高版本，软件会提示下载，下载后可“重启安装”。

## 配置说明

- CI 会根据 `GITHUB_REPOSITORY` 自动写入 GitHub 更新源。
- 本地手动打包时，需要把 `desktop/update-config.json` 里的 `owner` 和 `repo` 改成真实 GitHub 仓库。
- 用户数据、教材、错题、向量库、`.env` 应保存在用户数据目录，安装包更新不能覆盖这些数据。
- `electron-updater` 必须放在 `desktop/package.json` 的 `dependencies`，不能只放在 `devDependencies`。

## 不建议的更新方式

不要让用户点击更新后执行 `git pull`、`npm install`、`pyinstaller`。普通用户机器通常没有这些开发环境，而且容易覆盖本地数据。