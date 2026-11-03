# Back up and recover Airglow

A NixOS generation rollback restores software and service definitions. It does not restore mutable Airglow settings or LedFX data. Keep a matching private backup before switching releases.

The web **Backup & restore** tab exports only Airglow settings. It is useful for moving receiver/actions settings, but it is not a complete appliance backup.

## Create a consistent private backup

Run this on the Airglow host. It briefly stops the receiver and all configuration writers. The archive includes passwords and private host configuration. Store a copy outside the VM and never upload it to an issue or release.

```sh
sudo bash -eu <<'SH'
umask 077
install -d -m 0700 /var/backups/airglow
backup_file="/var/backups/airglow/airglow-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
trap 'systemctl start airglow-receiver-settings.path airglow-actions pulseaudio nqptp shairport-sync ledfx airglow' EXIT
systemctl stop airglow airglow-actions shairport-sync ledfx airglow-receiver-settings.path
tar -czpf "$backup_file" -C / var/lib/airglow/airglow.json var/lib/ledfx etc/nixos
gzip -t "$backup_file"
tar -tzf "$backup_file" >/dev/null
printf 'Verified private backup: %s\n' "$backup_file"
SH
```

Also preserve referenced host-configuration and credential files stored outside `/etc/nixos`, and record the active system path with `readlink -f /run/current-system`. Keep the current and previous release backups. Delete older copies only after recovery is verified and an off-VM copy exists.

## Roll back software

If the new software fails, use the previous NixOS generation:

```sh
sudo nixos-rebuild switch --rollback --no-reexec
```

The `--no-reexec` option uses the installed recovery command without fetching a channel or flake first.

If the machine cannot boot, select the previous generation from its boot menu. Check the version shown in Airglow and its diagnostics after rollback. Restore the previous private host flake and lock before the next build; otherwise the next rebuild will select the newer release again.

## Restore matching data

Use only your own verified backup. First select the matching software generation. The archive's `/etc/nixos` copy is retained for manual host recovery; the commands below restore application data only.

Run as root on the host. Replace `backup_file` with the verified archive. The current directories are moved aside, not deleted. The timestamped previous copies are private and should be removed only after the restored installation is checked.

```sh
backup_file=/var/backups/airglow/airglow-YYYYMMDDTHHMMSSZ.tar.gz
gzip -t "$backup_file"
tar -tzf "$backup_file"
systemctl stop airglow airglow-actions shairport-sync ledfx airglow-receiver-settings.path
restore_stamp=$(date -u +%Y%m%dT%H%M%SZ)
mv /var/lib/airglow "/var/lib/airglow.before-restore-$restore_stamp"
mv /var/lib/ledfx "/var/lib/ledfx.before-restore-$restore_stamp"
tar -xzpf "$backup_file" -C / var/lib/airglow/airglow.json var/lib/ledfx
chown -R airglow:airglow /var/lib/airglow
chmod 750 /var/lib/airglow
chown -R ledfx:ledfx /var/lib/ledfx
systemctl start airglow-receiver-settings.path airglow-actions pulseaudio nqptp shairport-sync ledfx airglow
```

If extraction fails, keep services stopped. Move the incomplete directories aside and put the `.before-restore-*` directories back before restarting. Never copy `/run/airglow` from a backup; receiver sessions and events belong to the current boot.

Confirm the receiver name, password state, action choices and LedFX devices/effects. Check ownership and real playback. Automatic tests rehearse application-data restoration, reboot persistence and software-generation rollback; they do not replace your off-VM backup or physical playback check.
