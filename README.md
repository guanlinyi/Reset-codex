# Reset-codex

English | [简体中文](README.zh-CN.md)

A Windows 11 quota dashboard and continuation tool for Codex. Monitor five-hour and weekly limits, manage native Codex terminals through Psmux, and continue work after quota recovery. The app is named **Reset**, defaults to Chinese, and supports English. VS Code is not required.

## Get started

[Download the Windows x64 portable package](release/Reset-codex-windows-x64.zip)

1. Extract the package and double-click `Reset.exe`. Keep the helper executable and `_internal` alongside it. Python and Psmux are included.
2. Wait for automatic checks. Reset reuses an existing Codex sign-in and lists recent local CLI conversations by title and full session ID. Use **Connection & startup** to install or locate Codex and Windows Terminal when missing.
3. Keep the default conversation or select another one, then click **View**. The native chat opens in a black Windows Terminal window.
4. Edit the **Continuation message** if needed, choose how many quota recoveries to wait for, and click **Start continuous work**. Reset inputs and submits the message automatically. Subsequent recovery rounds use the same message.

The prefilled message is:

> 持续推进至额度耗尽，确认独立任务结束后保存交接

It asks Codex to continue until quota exhaustion and save a handoff after completing independent tasks. Replace it with your own instruction, up to 2000 characters. The optional model selector changes the model only when explicitly selected; otherwise the conversation keeps its own model.

## Continuous work

- **Recoveries default to 0:** stop automation when the current quota runs out. Choose 1 to wait for one confirmed five-hour quota recovery and continue for one more round. Each recovery submits the message once. A countdown alone does not prove recovery.
- **Dismiss the goal-resume prompt by default:** select `Leave paused`, then submit the continuation message. Uncheck this option to handle the prompt manually.
- **Update Codex automatically by default:** handle a recognized official update picker, confirm success and the old Codex process exiting, then resume the original session ID in the same Psmux terminal before submitting the message. Uncheck to handle updates manually. Unsupported menus, failures and timeouts stop automation rather than retrying indefinitely.
- **Shutdown defaults to off:** when enabled, the final quota exhaustion and an idle terminal start a cancellable 60-second countdown. Quota is checked again before shutdown. With 0 recoveries, shutdown follows the current round; with 1, it follows the final round after one recovery.
- **Cancel continuous work:** stop future continuation and shutdown. Already submitted Codex work keeps running. Use the conversation's **End** control to stop its terminal and work.

Reset keeps the computer awake while continuous mode is active. Closing a terminal, shutting down Windows, permission prompts or other conditions requiring attention can interrupt the workflow. Restarting Reset does not automatically restart continuous work. A complete real-account exhaustion → waiting → recovery cycle still requires further live validation; see [Validation scope](VALIDATION.md).

## Terminal management

**View** reconnects an existing Reset-managed Psmux conversation or creates a terminal when it is not running. Launches for the same session ID are serialized. An attached session uses its existing window rather than starting another Codex.

**Running conversations** lists managed Psmux terminals with titles, full session IDs, PIDs and connection status. **End** asks for confirmation, stops that conversation's continuation controller and closes its terminal while preserving saved history. Batch end includes only confirmed detached sessions and rechecks their identities before closing; reconnected or changed targets are skipped.

External conversations are identified using launch arguments, registered identities and persistently held writable session-file handles. This inspects filenames and handle permissions, not file contents. If the selected conversation is identified in an external terminal, Reset asks you to close the original Codex first. Unidentified unrelated processes do not block every conversation. Permissions, custom data directories and unsupported clients can limit detection.

Closing the last frontend terminal ends its Psmux backend; minimizing does not. Reset will not blindly overwrite pending input or operate a changed terminal registration. If the exact configured message remains from a previous attempt, it attempts to submit that draft rather than typing it again.

## Connection, network and startup

Use the **＋／−** beside **Connection & startup** to expand or collapse setup checks. Existing official Codex authentication is reused. If sign-in is missing, click **Sign in with ChatGPT** and complete official authorization yourself. Reset does not import all conversations from the ChatGPT website.

**A proxy is optional.** Without one, Reset connects directly. It follows existing proxy environment variables or Windows system settings and can discover ports for supported running local proxy clients. Enter an HTTP proxy URL only when needed and automatic discovery fails. Public defaults contain no personal port, and URLs with embedded credentials are not accepted. Quota-query failures do not prevent the local conversation list from loading.

**Open Reset at sign-in** starts only Reset after Windows login. It does not restore a chat or submit a task. Dependency installation, Windows elevation and scoped executable-permission repair use interface controls and user-confirmed system authorization. Repair does not relax profile-directory permissions or Codex sandbox settings.

## Local data and privacy

Personal configuration is stored in `%LOCALAPPDATA%/Reset/config.local.json`, with runtime and interface data in the local application-data directory. Continuation messages and checkbox settings are stored in local continuous-mode state, not public defaults or portable-package resources. A `config.local.json` alongside the app is also supported; application-data overrides take precedence.

Quota, models and recent conversation titles come from the local official Codex app-server without directly opening authentication files. Prompt handling and submission verification capture the selected Psmux terminal's visible screen locally, which may contain conversation text. Reset does not upload those captures or save them as logs. Instructions submitted to Codex are processed by official Codex through its normal operation.

Do not commit personal configuration, authentication files, browser data, runtime records or personal progress notes. Ignore rules and a public-content audit are included.

| Advanced setting | Purpose |
|---|---|
| `codex_path`, `windows_terminal_path`, `browser_path`, `psmux_path` | Locate executables if automatic discovery fails. |
| `workspace` | Leave blank for all local CLI conversations or filter by working directory. |
| `thread_id` | Optional default conversation; blank selects the most recent usable one. |
| `language` | `zh` or `en`; interface selection is remembered locally. |
| `recovery_limit` | Default recovery count, from 0 to 100. |
| `proxy_host`, `proxy_port` | Optional; fill both or leave blank for discovery or direct access. |
| `require_admin` | Check administrator permissions and actual Windows integrity level. |
| `startup_delay_seconds` | Delay after Windows sign-in, default 10 seconds. |

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

