# Validation scope

The current Windows build has passed initial user acceptance for the interface and basic continuation workflow. This is not a claim that every recovery, update or shutdown scenario has been verified live.

## Verified in live operation

- A selected existing Codex conversation opens in a black Windows Terminal through Psmux. The backend Codex process and attached Psmux client were checked.
- The prescribed Leave paused → continuation-message sequence was demonstrated and confirmed by the user during development. A later overlay-layout regression was identified from an authorized terminal inspection and covered by a synthetic regression test.
- A manually opened external Codex conversation was associated with its process using writable session-file handle metadata. The open guard returned an external-terminal warning and did not create another terminal.
- Startup behavior and scoped permission repair have been exercised on Windows. Startup opens Reset without automatically submitting work.

## Automated and synthetic checks

- All 104 public automated checks pass. They cover configuration/privacy defaults, quota state transitions, cancellation, terminal ownership, exact close targets, duplicate guards, detach policy, file-handle identity inference, message submission and update handling.
- Message tests cover overlay goal prompts, unchecked automatic handling, editable multiline instructions, Enter submission, a retained exact draft, retrying Enter without typing a duplicate message, and failure when submission remains unconfirmed.
- Update tests cover a supported official picker, success followed by the same session ID, disabled automatic updates, failures, timeouts and repeated-prompt prevention. Update commands and power actions are mocked in tests.
- Synthetic browser checks verify default checked options, editable instructions, request parameters, Chinese/English switching and a narrow-window layout. Rendered interface screenshots were visually inspected.
- Public-content and portable-package checks exclude local configuration, authentication files, conversation state, experimental artifacts and personal progress documents.

## Still requires live validation

- A complete real-account quota exhaustion → waiting → confirmed recovery → automatic continuation cycle.
- The next actual Codex update, including its exact UI/version and installer behavior. Current update-transition checks use fixtures; an available real update was not forced.
- Automatic shutdown after the final quota round. Automated tests use a fake power action, never a real shutdown.
- Changed Codex UI versions, custom installation/data paths and permission environments beyond the tested machine.

The app stops with a visible error when terminal state or submission cannot be confirmed. Session detection is best-effort when OS access is restricted or a client does not expose a supported identity signal.
