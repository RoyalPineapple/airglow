# LedFx AirPlay - Docker Compose Stack

Stream audio from any AirPlay device to LedFx for real-time LED visualization.

## Architecture

```
AirPlay Device (iPhone/Mac)
    ↓ (AirPlay 2)
Shairport-Sync (AirPlay Receiver)
    ↓ (PulseAudio)
LedFx (Audio Visualization)
    ↓ (E1.31/UDP)
LED Strips/Devices
```

**How it works:**
- **Shairport-Sync** receives AirPlay audio streams and outputs to PulseAudio
- **LedFx** runs a PulseAudio server that Shairport connects to via Unix socket
- **No ALSA configuration needed** - PulseAudio handles all audio routing
- **Network mode: host** - Services use host networking for mDNS discovery and LED protocols

## Prerequisites

- Linux host (Debian/Ubuntu recommended)
- Docker Engine + Docker Compose
- Network access for mDNS (AirPlay discovery)

## Quick Start

### Method 1: Docker Compose (Manual)

1. Clone or download this directory
2. Start the stack:
   ```bash
   docker compose up -d
   ```
3. Check status:
   ```bash
   docker compose ps
   docker compose logs
   ```
4. Open LedFx web UI: `http://localhost:8888`

### Method 2: Install Script (Automated)

Run the installer which handles Docker installation and setup:
```bash
./install.sh
```

## Configuration

### AirPlay Device Name
Edit `configs/shairport-sync.conf` and change the `name` field:
```
general = {
    name = "LEDFx AirPlay";  // Change this
    ...
}
```

### Audio Settings
In the LedFx web UI (Settings → Audio):
1. Select "pulse" from the audio device dropdown
2. Click "Save" to apply

This connects LedFx to the PulseAudio monitor that receives audio from Shairport.

### LED Devices
1. Open LedFx web UI: `http://localhost:8888`
2. Navigate to Devices section
3. Add your WLED/E1.31 devices
4. Configure effects and start visualizing

## Troubleshooting

### Check Services
```bash
# View container status
docker compose ps

# View logs
docker compose logs -f ledfx
docker compose logs -f shairport-sync
```

### Verify AirPlay Discovery
The AirPlay device "LEDFx AirPlay" should appear in your device's AirPlay menu. If not:
- Check that containers are running (`docker compose ps`)
- Verify network mode is `host`
- Ensure mDNS/Avahi is working on your network

### Check Audio Flow
Inside the LedFx container:
```bash
# List PulseAudio sources
docker exec ledfx pactl list sources short

# Check for Shairport audio stream
docker exec ledfx pactl list sink-inputs
```

You should see a "Shairport Sync" sink input when audio is playing.

### Debug PulseAudio
```bash
# Check Pulse socket
ls -la pulse/

# Verify Pulse server in LedFx
docker exec ledfx pactl info

# Check Shairport Pulse connection
docker logs shairport-sync | grep -i pulse
```

### Common Issues

**AirPlay device not showing up:**
- Restart containers: `docker compose restart`
- Check firewall allows mDNS (port 5353/UDP)

**No audio in LedFx:**
- Verify audio is playing to the AirPlay device
- Check PulseAudio sink-inputs (see above)
- In LedFx UI, confirm audio device is set to "pulse"

**Permission errors:**
- Ensure `pulse/` directory has correct permissions:
  ```bash
  sudo chown -R 1000:1000 pulse/
  ```

## Updating

Pull latest images and restart:
```bash
docker compose pull
docker compose up -d
```

## Ports

- **8888** - LedFx web UI (HTTP)
- **7000** - Shairport-Sync AirPlay (TCP)
- **5353** - mDNS/Avahi discovery (UDP)

## Architecture Details

### PulseAudio Bridge

This setup uses a PulseAudio socket to route audio between containers:

1. LedFx container runs PulseAudio in server mode
2. Creates socket at `./pulse/pulseaudio.socket`
3. Shairport-Sync connects as Pulse client via this socket
4. LedFx reads from the Pulse monitor source (`auto_null.monitor`)

**Benefits:**
- No ALSA loopback configuration needed
- Clean container isolation
- Reliable audio routing
- Easy to debug with `pactl` commands

### Why Host Networking?

- **mDNS Discovery**: AirPlay uses mDNS/Bonjour for device discovery
- **E1.31/UDP**: LED protocols work better with direct host access
- **Simplified Routing**: No port mapping needed

## License

MIT - Feel free to use and modify

