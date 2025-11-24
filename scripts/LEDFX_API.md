# LedFx API Documentation Summary

Based on official documentation: https://docs.ledfx.app/en/latest/apis/api.html

## Key Endpoints for Session Control

### Virtuals Control

#### GET /api/virtuals
Get configuration of all virtuals

#### GET /api/virtuals/{virtual_id}
Returns information about a specific virtual

#### PUT /api/virtuals/{virtual_id}
**Set a virtual to active or inactive**

Example to deactivate:
```json
{
  "active": false
}
```

Example to activate:
```json
{
  "active": true
}
```

#### DELETE /api/virtuals/{virtual_id}/effects
**Clear the active effect of a virtual** (stops visualization)

This removes the effect but keeps the virtual active.

### Effects Control

#### GET /api/virtuals/{virtual_id}/effects
Returns the active effect config of a virtual

#### POST /api/virtuals/{virtual_id}/effects
Set the virtual to a new effect based on JSON configuration

#### PUT /api/virtuals/{virtual_id}/effects
Update the active effect config of a virtual

#### DELETE /api/virtuals/{virtual_id}/effects
Clear the active effect of a virtual

## Strategy for AirPlay Session Hooks

**To Start Visualization:**
- Ensure virtual is active: `PUT /api/virtuals/{virtual_id}` with `{"active": true}`
- If no effect is active, we may need to restore the last effect or apply a default

**To Stop Visualization:**
- Option 1: Deactivate virtual: `PUT /api/virtuals/{virtual_id}` with `{"active": false}`
- Option 2: Clear effect: `DELETE /api/virtuals/{virtual_id}/effects`

**Recommended Approach:**
- On AirPlay start: Activate virtual (if inactive) and ensure effect is running
- On AirPlay stop: Clear effect (this stops visualization but preserves the effect config for next time)

