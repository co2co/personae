# 群像弈（Personae）【暂定】安装指南

本指南面向**拿到分发包的用户**：你只需要 `engine/` 这一份目录即可独立运行，无需 Python 工程经验。
全程图形化（双击 `.bat`）即可，命令行仅作备选。

---

## 1. 系统要求

- 操作系统：Windows 10 / 11（macOS、Linux 同样可用，命令见第 3、4 节的「跨平台」备注）
- Python：**3.10 及以上**（推荐 3.12，[python.org](https://www.python.org) 或 Microsoft Store 均可）
- 网络：首次安装依赖、以及调用云端大模型时需要联网

---

## 2. 下载与解压

1. 拿到分发包 `personae-vX.Y.zip`。
2. 解压到任意目录（建议路径不含中文与空格，最稳妥）。解压后得到 `engine/` 目录。

> **解压工具注意**：请用 **Windows 资源管理器的「全部解压缩」** 或 **7-Zip** 解压。
> 不要用 Git Bash 里的 `unzip` 等老式工具——它们可能把中文文件名解成乱码。
> （乱码仅影响文件显示名，不影响引擎运行；但为避免困惑，请用上述两种工具。）

---

## 3. 安装依赖（只需做一次）

进入 `engine/` 目录，双击 **`install.bat`**。它会自动完成：

1. 探测 Python（优先 `py -3`，否则用 `python`）；
2. 在 `engine/` 内创建虚拟环境 `engine/venv`；
3. 用 pip 安装 `requirements.txt` 里的依赖（Flask、requests）。

看到「依赖安装成功」即可。

**如果 `install.bat` 失败**，可手动安装：

```bat
cd engine
python -m venv venv
venv\Scripts\pip install -r requirements.txt
```

**macOS / Linux（跨平台）：**

```bash
cd engine
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 4. 启动引擎

两种方式任选其一：

- **图形化**：双击 `engine/run.bat`（默认端口 **5051**）。
- **命令行**：

  ```bat
  cd engine
  python app.py                 # 默认 http://127.0.0.1:5000
  ```

  想换端口，启动前设环境变量即可：

  ```bat
  set PORT=8080
  python app.py
  ```

看到终端输出 `Running on http://127.0.0.1:5051` 即启动成功。
（`run.bat` 若发现端口被占用，会先尝试关闭占用进程再启动；手动 `python app.py` 则需自己换端口。）

---

## 5. 打开使用

浏览器访问对应地址（默认 `http://127.0.0.1:5051` 或 `http://127.0.0.1:5000`）。

顶部四个面板：

- **角色库**：新建 / 编辑 / 删除角色卡，或「导入 JSON」从外部导入（未识别字段会保留）。
- **世界书**：编辑世界书条目；点「世界书说明书」内链可看完整用法（浏览器打开 `/docs/worldbook`）。
- **会话**：列出 / 继续 / 放弃进行中的剧本。
- **系统设置**：配置大模型与生成参数。

关掉终端窗口或按 `Ctrl+C` 即停止服务。

---

## 6. 配置大模型（系统设置面板）

引擎通过 **OpenAI 兼容接口** 调用大模型，在「系统设置」面板填写：

- `base_url`：接口地址（默认对接 SiliconFlow，也可填本地 llama.cpp / 中转代理）
- `model`：模型名（如 `tencent/Hy4-preview`）
- `api_key`：你的密钥

修改后点保存即可生效，**无需重启**。

> 没有密钥也能启动引擎、浏览界面与编辑内容；只是「开始推演」调用模型时会报错。

---

## 7. 你的创作内容在哪

所有数据都是 `engine/` 下的本地文件，无数据库：

- `data/characters/*.json` —— 角色卡（**文件名即角色显示名**，可自行添加）
- `data/worlds/*.json` —— 世界书（可自行添加）
- `data/config.json` —— 系统配置（出厂为空连接）

**分发包不含示例剧本**，首次运行需自行导入角色卡/世界书（`data/characters/`、`data/worlds/` 下的内容由你自己创作，不会被打进分发包）。`player-cast/`（玩家设定）也始终不随包分发。
（运行时产生的会话记录在 `data/sessions/`，状态在 `data/state.json`——这些也不会被打进分发包。）

---

## 8. 常见问题

- **端口被占用**：`run.bat` 会自动 kill 占用进程；手动启动时改 `PORT` 环境变量即可。
- **找不到 Python**：把 Python 3.10+ 加入系统 PATH，或安装 Microsoft Store 版 Python。
- **依赖安装慢 / 失败**：检查网络或代理；可配置 pip 镜像源（如清华、阿里云镜像）。
- **启动后浏览器打不开**：确认地址与端口正确、系统防火墙未拦截本机回环地址。
- **`/docs/worldbook` 打不开（500）**：说明 `static/worldbook-guide.html` 缺失或被改名，重新解压分发包即可。

---

## 9. 升级

拿到新版本分发包后，直接**覆盖**旧 `engine/` 即可。
若你已积累了角色/世界书/会话，升级前建议先备份 `engine/data/`；覆盖时保留你的 `data/`，只更新代码与前端。

---

更完整的机制说明见浏览器 `/docs/worldbook`（世界书）；`DEVLOG.md` 为版本与架构演进记录（不随分发提供）。
