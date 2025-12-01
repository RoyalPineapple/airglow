# AirPlay Feature Flags Documentation

## Overview

AirPlay devices advertise their capabilities using feature flags in their mDNS TXT records. These flags are extracted from the `ft=` field and displayed in the AirPlay Browser.

## Format

Feature flags are represented as **two 32-bit hexadecimal values**, separated by commas:
- Example: `0x4A7FDFD5,0x3C177FDE`
- First value: Primary feature set
- Second value: Secondary feature set / extended capabilities

## Source

Feature flags are extracted from the mDNS TXT record during service discovery:
- **Service Type**: `_raop._tcp` (AirPlay 2 audio) or `_airplay._tcp` (AirPlay 1)
- **Field**: `ft=` (feature flags)
- **Method**: Parsed from `avahi-browse` output using regex: `r'"ft=([^"]+)"'`

## Known Feature Bits

### For `_airplay._tcp` (Video/Photo Service)

While your devices primarily use `_raop._tcp`, these are the documented bits for the video service:

- **Bit 0 (0x00000001)**: Video support
- **Bit 1 (0x00000002)**: Photo support
- **Bit 2 (0x00000004)**: Video protected with FairPlay DRM
- **Bit 3 (0x00000008)**: Video volume control support

### For `_raop._tcp` (Audio Service)

The exact bit meanings for RAOP feature flags are **not fully documented** by Apple. However, they likely indicate:

1. **First Flag (0x4A7FDFD5)**: 
   - Audio codec support (ALAC, AAC, PCM)
   - Protocol version support
   - Encryption capabilities

2. **Second Flag (0x3C177FDE)**:
   - AirPlay version support (1 vs 2)
   - Additional protocol features
   - Extended capabilities

## Current Implementation

### Extraction
- **Location**: `airglow/web/app.py` → `parse_avahi_browse_output()`
- **Method**: Regex extraction from TXT record: `ft_match = re.search(r'"ft=([^"]+)"', txt_record)`
- **Storage**: Stored as raw string in device data structure

### Display
- **Location**: `airglow/web/templates/browser.html`
- **Format**: Displayed as `<code>` formatted hex values in the "Features" column
- **Fallback**: Shows `—` if no feature flags are present

## Example Values from Your Network

```
Living room 2!: 0x4A7FDFD5,0x3C177FDE
Bedroom: 0x4A7FCA00,0x3C354BD0
MacBook Pro: 0x4A7FCFD5,0x38174FDE
Living room: 0x4A7FCA00,0x3C354BD0
Subwoofer: 0x445F8A00,0x4001C340
iPod HiFi: 0x445F8A00,0x4001C340
AirGlow: — (no flags - likely AirPlay 1 mode or missing TXT record)
```

## Observations

1. **Device Grouping**: Devices with identical flags (e.g., "Subwoofer" and "iPod HiFi") likely share the same hardware/firmware
2. **Pattern Recognition**: Similar devices show similar flag patterns (e.g., HomePods: `0x4A7FCA00,0x3C354BD0`)
3. **Missing Flags**: Some devices (like AirGlow) may not advertise feature flags, indicating:
   - AirPlay 1 mode
   - Incomplete TXT record
   - Build configuration issue

## Limitations

1. **Incomplete Documentation**: Apple does not publish complete bit mappings
2. **Reverse Engineering**: Most knowledge comes from community reverse engineering
3. **No Decoder**: Current implementation shows raw hex values only
4. **RAOP vs AirPlay**: Different services (`_raop._tcp` vs `_airplay._tcp`) have different flag meanings

## Future Enhancements

Potential improvements:
1. **Basic Decoder**: Identify common patterns (e.g., "AirPlay 2 supported" if certain bits are set)
2. **Bit Breakdown**: Show which bits are set in binary format
3. **Device Comparison**: Highlight devices with identical flags
4. **Human-Readable Labels**: Map known flag patterns to readable capabilities

## References

- [AirPlay Service Discovery](https://openairplay.github.io/airplay-spec/service_discovery.html)
- [AirPlay Internal Documentation](https://air-display.github.io/airplay-internal/service_discovery/airplay_tcp.html)
- Shairport-Sync: Open-source AirPlay implementation
- OpenAirPlay: Community reverse-engineered AirPlay specifications

## Related Code

- **Parser**: `airglow/web/app.py::parse_avahi_browse_output()` (lines 959-1089)
- **API Endpoint**: `airglow/web/app.py::get_airplay_devices()` (lines 1092-1170)
- **Frontend Display**: `airglow/web/templates/browser.html` (line 96)

