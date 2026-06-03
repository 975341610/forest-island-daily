============================================
  森林小岛日报 · Windows 使用说明
============================================

⚠️ 关于 .bat 文件
为避免 Windows cmd 的中文乱码问题（GBK / UTF-8 编码冲突），
所有 .bat 脚本内的提示都改成了英文。
本说明用记事本打开即可阅读中文。

============================================
  你有哪些脚本？
============================================

1. deploy.bat       —— 首次部署用，跟着 5 步走
2. push-today.bat   —— 日常更新用，每天双击一次
3. preview.bat      —— 本地预览，启 http://localhost:8000

============================================
  首次部署流程（只做一次）
============================================

第 1 步：去 GitHub 网页建一个空仓库
  - 打开 https://github.com/new
  - Repository name 填：forest-island-daily
  - 不要勾 README / .gitignore / license
  - 点 Create repository
  - 复制下一页给的仓库地址（HTTPS 或 SSH 都行）

第 2 步：双击 deploy.bat
  - 全程跟着英文提示走
  - 第 0 步会问 Have you created the empty repo? 输入 y 回车
  - 第 4 步让你粘贴仓库地址 → 右键粘贴
  - 最后会问 Open GitHub Pages settings now? 输入 y 才会开浏览器
    （默认 N，按回车不会自动开）

第 3 步：在浏览器里启用 GitHub Pages
  - 进入 Settings → Pages
  - Build and deployment → Source 下拉 → 选 GitHub Actions
  - 等 1-2 分钟，访问 https://你的用户名.github.io/forest-island-daily/

============================================
  日常使用流程（每天）
============================================

1. 飞书收到 Mira 发的 today.json 附件
2. 右键 → 另存为 → 保存到 工程文件夹\data\today.json
3. 双击 push-today.bat
4. 等 1-2 分钟，网页自动更新

============================================
  常见问题
============================================

Q: deploy.bat 运行后 git push 失败，要求输入密码？
A: GitHub 已不支持用密码 push，要用 Personal Access Token：
   1. 打开 https://github.com/settings/tokens
   2. Generate new token (classic) → 勾 repo 权限 → 生成
   3. 复制出来的 token（长得像 ghp_xxxxx）
   4. 在弹窗里：username 输 GitHub 用户名，password 粘贴 token

Q: 双击 .bat 后窗口一闪就关？
A: 在文件夹空白处 Shift + 右键 → 在此处打开 PowerShell 窗口
   然后输入：.\deploy.bat
   有错误就不会自动关，看得清原因

Q: 想看本地效果，直接打开 index.html 是空的？
A: 浏览器 file:// 协议禁止 fetch 本地文件。
   双击 preview.bat 启本地服务器，就能看到了。

Q: 提示找不到 python？
A: 去 https://www.python.org/downloads/ 装 Python 3
   安装时勾上"Add Python to PATH"

Q: 提示找不到 git？
A: 去 https://git-scm.com/download/win 装 git
   一路 Next 即可
