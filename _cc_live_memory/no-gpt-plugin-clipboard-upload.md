---
name: no-gpt-plugin-clipboard-upload
index_summary: "插件 file_upload 10MB 上限且拒主机路径别用;改走 clip_send.ps1 -Files(必须 DataObject+SetDataObject copy:=true)聚焦输入框 Ctrl+V;长 prompt 同理;sandbox 附件几分钟 404 完成立即收"
description: "托底通道手动上传姿势:插件 file_upload 工具 10MB 上限且拒收主机路径别用;改走 Windows 剪贴板 clip_send.ps1 -Files(必须 DataObject+SetDataObject copy:=true 冲刷,别裸调 SetFileDropList)聚焦 ChatGPT 输入框 Ctrl+V;长 prompt 同理 Set-Clipboard -Value;LZMA zip 让对方用 python -m zipfile -e 解;sandbox 附件几分钟回收 404 完成立即收"
metadata:
  node_type: memory
  type: feedback
---

**插件手动上传姿势(托底通道用):** 插件 `file_upload` 工具 10MB 上限且新版拒收主机路径——别用它。走 Windows 剪贴板:用 `C:\Users\22957\clip_send.ps1 -Files <path>`(**别裸调 SetFileDropList——其数据随设置进程退出消失,必须 DataObject + SetDataObject(copy:=true) 冲刷,脚本已内置**;`Set-Clipboard -Path` 是 5.1 专属),聚焦 ChatGPT 输入框发 Ctrl+V(14.2MB 实测成功,网页上限 512MB)。长 prompt 同理 `Set-Clipboard -Value` + Ctrl+V。LZMA zip 让对方用 `python -m zipfile -e` 解(Linux unzip 不支持)。**sandbox 附件几分钟就回收(404)**:完成后立即收,收不到就追问一句让 GPT 重新生成(沙盒重建文件)。
