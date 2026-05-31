# CC SessionEnd hook: session 优雅退出时, 若有未提交改动则 commit WIP + 自动 push,
# 堵住"两次 commit 之间机器死掉丢未提交的活"的窗口。
# 注: 机器崩溃(进程被杀)时本 hook 不会 fire —— 崩溃靠 post-commit auto-push + 勤 commit 兜。
# commit 会触发 pre-commit(memory 同步) + post-commit(自动 push)。
$ErrorActionPreference = 'SilentlyContinue'
$repo = git rev-parse --show-toplevel 2>$null
if (-not $repo) { exit 0 }
Set-Location $repo
if (git status --porcelain) {
    git add -A
    git commit -m "chore: SessionEnd WIP auto-checkpoint" -m "auto by CC SessionEnd hook; 这类 WIP commit 要周期性 squash 整理 (见 memory github-backup)"
    # post-commit hook 自动 push, 此处不重复 push
}
exit 0
