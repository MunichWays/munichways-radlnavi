import React, { useState } from 'react';
import { IconButton, ListItemIcon, ListItemText, Menu, MenuItem, Tooltip } from '@mui/material';
import LayersOutlined from '@mui/icons-material/LayersOutlined';
import RadioButtonChecked from '@mui/icons-material/RadioButtonChecked';
import RadioButtonUnchecked from '@mui/icons-material/RadioButtonUnchecked';

export type MapBackground = 'standard' | 'reduced' | 'bavaria-aerial';

export default function MapBackgroundControl({ value, onChange, reducedLabel = 'Reduziert' }: {
  value: MapBackground;
  onChange: (background: MapBackground) => void;
  reducedLabel?: string;
}) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const open = Boolean(anchor);
  const choose = (next: MapBackground) => {
    if (next !== value) onChange(next);
    setAnchor(null);
  };
  return <>
    <Tooltip title="Kartenansicht auswählen">
      <IconButton id="map-background-button" aria-label="Kartenansicht auswählen"
        aria-haspopup="menu" aria-expanded={open}
        aria-controls={open ? 'map-background-menu' : undefined}
        onClick={event => setAnchor(event.currentTarget)}
        sx={{ position: 'absolute', top: 82, right: 10, zIndex: 1000,
          width: 44, height: 44, backgroundColor: 'white', boxShadow: 2,
          '&:hover': { backgroundColor: '#f5f5f5' } }}>
        <LayersOutlined />
      </IconButton>
    </Tooltip>
    <Menu id="map-background-menu" anchorEl={anchor} open={open}
      onClose={() => setAnchor(null)}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      transformOrigin={{ vertical: 'top', horizontal: 'right' }}
      MenuListProps={{ 'aria-labelledby': 'map-background-button' }}>
      {(['standard', 'reduced', 'bavaria-aerial'] as const).map(background => <MenuItem
        key={background} role="menuitemradio" aria-checked={value === background}
        selected={value === background} onClick={() => choose(background)}
        sx={{ minHeight: 48 }}>
        <ListItemIcon>{value === background ? <RadioButtonChecked /> : <RadioButtonUnchecked />}</ListItemIcon>
        <ListItemText>{background === 'standard' ? 'Standard' : background === 'reduced' ? reducedLabel : 'Luftbild Bayern'}</ListItemText>
      </MenuItem>)}
    </Menu>
  </>;
}
