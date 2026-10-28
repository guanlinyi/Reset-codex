# Validation scope

- 44 automated tests cover bounded quota recovery, cancellation, manual pause, restart safety, direct networking without a proxy, dynamic local-proxy discovery, independent local conversation loading, configuration defaults, local-service origin checks, and startup without conversation restoration.
- Public source and resource audit passes. The public defaults do not specify personal paths, a proxy port, a conversation, a model, or a workspace. Runtime state and local override files are excluded and are not included in this checkout.
- Both frozen EXEs pass resource/runtime smoke checks without starting Codex, reading chat content, or consuming model quota.
- The frozen Python code objects in both EXEs were inspected as well as the source/resource text. No original private configuration markers were found.
- Synthetic desktop Chinese and mobile English interfaces were rendered and visually inspected. Proxy fields remain empty. Configuration-selected language and a custom recovery count are tested.
- Integrity metadata is checked separately from the administrator flag. A Low label is detected; an explicit scoped repair script is provided. Repair does not change profile-directory permissions or Codex sandbox policy.
- Both frozen entry points and an isolated bundled Psmux → PowerShell → bundled terminal-helper chain were checked for High integrity. Repair is explicitly scoped to application executables.
- A real frozen-app integration check removed inherited proxy environment variables and used empty application configuration. The app discovered an available supported local proxy, reused an existing Codex ChatGPT sign-in, and loaded quota, recent conversation metadata, and the model catalog without starting a task.
- Onboarding sign-in and startup-toggle behavior were tested with mocked browser authorization and task registration. These checks did not install software, reset an account, or register a real startup task.

This is not evidence of a complete real-account exhaustion → waiting → recovery cycle. That scenario and changing native Codex UI versions still require live acceptance. No GitHub upload, startup registration, real conversation restoration, or model request was performed as part of preparing this public tree.
