# Manifest Reference

Required fields: `manifest_version`, `id`, `name`, `version`, `publisher`, `description`, `runtime`, `entrypoint` and `platform_api`.

Plugin IDs use reverse-DNS form, for example `hu.codelayer.pin-configurator`. `provides` maps capability names to exact semantic versions. `requires` maps capability names to semantic-version requirements.

Contributions describe workbenches, commands, views and editors so the shell can render navigation without importing plugin code. Permissions are denied unless enabled in the manifest and allowed by organization policy.
