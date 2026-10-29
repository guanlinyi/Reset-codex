# Reset-codex

English | [简体中文](README.zh-CN.md)

A Windows quota dashboard and continuation tool for Codex. Monitor five-hour and weekly usage limits, reconnect to existing native conversations in VS Code, and continue work after a chosen number of quota recoveries. The app is displayed as **Reset** and supports Chinese and English.

## Get started

[Download the Windows x64 portable package](release/Reset-codex-windows-x64.zip)

1. Extract the portable package and double-click `Reset.exe`. Keep `_internal` and the helper executable alongside it. Python and Psmux are included.
2. Wait for the automatic checks. Reset reuses an existing Codex sign-in and lists recent local conversations. There is no need to import session files or enter conversation IDs.
3. Keep the default conversation or select another one, choose how many quota recoveries to wait for, and click **Start continuous work**. Click **Cancel continuous work** to stop automatic continuation.

The default is **0 recoveries**: stop when the current quota runs out. Select **1 recovery** to wait for one confirmed recovery and continue. Completion, a manual pause, or a condition requiring attention can stop work earlier. Reset keeps the system awake while continuous mode is active.

The interface initially uses Chinese. Select **English** in the top-right language menu to switch; the choice is remembered locally.

### If something is missing on first launch

Manual configuration is normally unnecessary. **Connection & startup** expands when an action is needed:

| Situation | Action |
|---|---|
| Codex or VS Code was not found | Click **Install**, or **Choose program** to locate an existing installation. |
| No existing sign-in is available | Click **Sign in with ChatGPT** and complete the official browser authorization once. Existing Codex sign-ins are reused automatically. |
| An application file has a restricted integrity label | Click **Repair app permissions** and confirm the Windows prompt. |
| The apps should open at Windows sign-in | Enable **Open Reset and VS Code at sign-in**. |
| A connection is temporarily unavailable | Click **Check again**. Use the optional network settings only if needed. |

Install actions use Windows Package Manager and ask for confirmation first. If the package manager is unavailable, Reset opens an official installation page. Windows elevation and account authorization remain under the user's control.

Startup opens Reset and VS Code only. It does not restore a conversation or start work; the Start button is still required.

## Automatic network discovery

**A proxy is optional.** Without one, Reset connects directly. It follows configured proxy environment variables or a Windows system proxy. For supported running local proxy clients, it can also discover listening ports and verify a TLS connection to the official authentication service. No personal port is hardcoded, and proxy configuration files are not read.

Supported clients include Clash/Mihomo, v2ray/Xray, sing-box, Geph, and others. If automatic discovery fails and the network actually requires a proxy, paste an HTTP proxy URL into **Connection & startup**. URLs containing usernames or passwords are not supported. Separate proxy host and port fields, along with model options, remain available in the advanced settings.

Local conversation metadata and remote quota are fetched independently. A quota or network failure does not prevent the local conversation list from loading.

## Conversations and sign-in

Reset uses the locally installed official Codex app-server to reuse Codex authentication and request quota, models, and recent CLI conversation titles. It does not import the full chat history from the ChatGPT website or directly open authentication files. Conversation execution stays in the selected native Codex terminal.

Each conversation row has **View** and **End** controls. View reconnects an existing Reset terminal, returns to a uniquely identified external terminal window, or opens a new terminal when the conversation is not running. End is disabled when there is no running target to stop.

Use **Check running conversations** to list Reset-managed terminals and detected external chat processes. Each PID is shown with its conversation title when an exact identity is available. Codex app-server, MCP, execution-service, and application-internal processes are filtered separately from chat terminals. Ordinary VS Code terminals and Psmux-hosted sessions are distinguished; an unrelated unidentified process does not disable all conversation rows. A retained shell can appear after Codex has exited.

Explicit resume IDs and the current native ancestor's exported identity can associate a process with its title. If a process has no confirmed conversation identity, the list states that clearly. Reset does not guess from the most recent title. If a new terminal could duplicate an unidentified existing conversation, View asks for confirmation instead of disabling the button or silently starting a duplicate.

**Reconnect** opens a fresh VS Code viewer attached to the original Psmux session. It can reconnect even when the previous workspace remains open but its terminal was closed; it does not start another Codex for an already-running conversation. Repeated reconnect requests can open additional VS Code viewer windows. Workspace-trust or automatic-task prompts must be reviewed by the user.

**End terminal** asks for confirmation, stops continuous work for that conversation, and ends only its verified Reset-managed Psmux session. Running work and unsent terminal input are interrupted; saved conversation history and project files remain. Other VS Code windows are not closed. Refresh the running list if the process changed before confirmation.

For an external conversation, **End** stops the selected Codex PID after checking its creation time and identity; its original terminal or VS Code window remains. View does not start a second Codex when a matching process exists. If its original window cannot be uniquely located, Reset explains how to end that process and reopen the conversation through Reset. Continuous work requires a Reset-managed terminal.

**End all background chats** first shows titles and PIDs for confirmation. It includes only Reset-managed sessions confirmed to have no connected frontend. Connected, unidentified, external, and internal-service processes are not included. The connection and identity are checked again before each close; reconnected or changed targets are skipped. Plans expire after 90 seconds and cannot be replayed.

Closing the last attached conversation terminal, or the VS Code window that owns it, automatically ends that session and stops its continuous-work controller. Minimizing the window does not end it. This disconnect policy is armed only after a real attachment and is enforced by Psmux even if Reset is no longer running. Legacy sessions left by an earlier version can still be found, reconnected, or ended through the running-conversation list; reconnecting applies the new policy.

If terminal ownership is uncertain, input is pending, authorization is required, or another condition needs attention, Reset stops rather than guessing where to type or approving requests automatically. Restarting the app does not automatically resume continuous work.

## Local configuration and privacy

The public `config.json` contains generic defaults. Program paths, model overrides, workspace, proxy settings, and the default conversation can all remain blank. Settings saved through the interface go to `%LOCALAPPDATA%/Reset/config.local.json`; runtime state is stored in the same local application-data directory, outside the source tree and portable package.

A `config.local.json` next to the app is also supported for portable or advanced use. Overrides in the user's local application-data directory take precedence. Do not commit personal configuration, authentication files, browser data, or runtime records. The repository includes `.gitignore` rules and a public-content audit for common local files.

| Advanced setting | Purpose |
|---|---|
| `codex_path`, `vscode_path`, `browser_path`, `psmux_path` | Specify executable paths if automatic discovery fails. |
| `workspace` | Leave blank to list all local CLI conversations, or filter by working directory. |
| `model`, `effort` | Leave blank to follow Codex or the existing conversation settings. |
| `thread_id` | Optional default conversation; blank selects the most recent usable conversation. |
| `language` | `zh` or `en`; a manual interface selection is remembered locally. |
| `recovery_limit` | Default number of quota recoveries to wait for, from 0 to 100. |
| `proxy_host`, `proxy_port` | Optional; fill both or leave both blank for discovery or direct access. |
| `require_admin` | Check administrator permissions and the actual Windows integrity level. |
| `startup_delay_seconds` | Delay after Windows sign-in; defaults to 10 seconds. |
| `startup_open_vscode` | Whether startup also opens an empty VS Code workspace. |

## Development and fallback commands

Windows 11 x64 and Python 3.11 or later are required for source development. An isolated Conda environment is recommended. The portable package includes Python 3.12.

Run from source:

```powershell
python -m pip install -r requirements.txt
python -B main.py
```

Build a new portable directory:

```powershell
python -m pip install -r requirements-build.txt
python -B build.py
```

The output is `release/Reset`. The build does not overwrite an existing output directory; use `--output` to choose a new one. `Reset.exe` is the desktop entry point. `ResetTerminal.exe` preserves native terminal input and output. Both use the same control logic.

These commands are alternatives to the interface controls:

```powershell
.\ResetTerminal.exe --diagnose
.\Reset.exe --install-startup
.\Reset.exe --disable-startup
```

Permission repair is also available from an elevated terminal:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\repair-permissions.ps1
```

The repair adjusts integrity labels on this application's executables only. It does not recursively modify directories, relax profile-directory ACLs, or change the Codex sandbox. The script verifies the Psmux signature. Integrity labels belong to the local filesystem: newly built or copied files can inherit restrictions from their destination. Repairing an old copy does not automatically repair a new copy, but repair is not required on every launch.

Run the automated checks and public-content audit:

```powershell
python -B -m unittest discover -s tests -q
python -B audit_public.py
```

Automated checks cover the state machine, cancellation, network discovery, configuration, and interface behavior. A complete real-account quota exhaustion, wait, and recovery cycle still requires live acceptance. If a Codex update changes the native interaction format, Reset stops for review.

## License

Project source is available under the MIT license. Third-party components retain their respective licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Reset-codex is an independent project and is not an official OpenAI application.

