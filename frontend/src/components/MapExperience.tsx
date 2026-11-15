import { ClientOnly } from '@tanstack/react-router';
import { lazy, Suspense, useState } from 'react';
import { PanelLeftOpen, Satellite, Map as MapIcon, SlidersHorizontal, X } from 'lucide-react';
import { InfoPanel } from './SidePanels';
import { usePlatform } from './PlatformContext';
import { Button } from './ui/button';

const MapView = lazy(() => import('./MapView'));

export function MapExperience() {
  const { place, selectPlace, hasSelectedLocation, setMapOpen } = usePlatform();
  const [panel, setPanel] = useState(false);
  const [layer, setLayer] = useState<'satellite' | 'map'>('satellite');
  const [indicator, setIndicator] = useState('all');
  return <main className="relative min-h-0 flex-1 overflow-hidden bg-muted" aria-label="Selecionar localização no mapa">
    <ClientOnly fallback={<div className="absolute inset-0 animate-pulse bg-muted"/>}>
      <Suspense fallback={null}><MapView place={place} layer={layer} onPick={selectPlace}/></Suspense>
    </ClientOnly>
    {panel ? <InfoPanel onClose={() => setPanel(false)} selectedIndicator={indicator}/> : <Button variant="outline" size="icon" aria-label="Abrir diagnóstico" title="Diagnóstico ambiental" onClick={() => setPanel(true)} className="absolute left-3 top-3 z-[1000] bg-card shadow-panel"><PanelLeftOpen/></Button>}
    <div className="absolute right-3 top-3 z-[1000] max-w-[calc(100vw-5rem)] space-y-2">
      <div className="ml-auto flex w-fit items-center gap-1 rounded-lg border border-border bg-card p-1 shadow-panel">
        {([['satellite',Satellite,'Satélite'],['map',MapIcon,'Mapa']] as const).map(([id,Icon,label]) => <Button key={id} size="sm" variant={layer===id?'default':'ghost'} onClick={() => setLayer(id)}><Icon/>{label}</Button>)}
        {hasSelectedLocation && <Button size="icon" variant="ghost" aria-label="Minimizar mapa" title="Minimizar mapa" onClick={() => setMapOpen(false)}><X/></Button>}
      </div>
      <label className="ml-auto flex w-fit max-w-full items-center gap-2 rounded-lg border border-border bg-card p-2 text-xs shadow-panel"><SlidersHorizontal className="size-4 shrink-0 text-primary"/><select aria-label="Indicador ambiental" value={indicator} onChange={e => setIndicator(e.target.value)} className="min-w-0 bg-background outline-none"><option value="all">Todos os indicadores</option>{[['temperature','Temperatura'],['precipitation','Precipitação'],['soil','Umidade do solo'],['wind','Vento'],['frost','Geada'],['altitude','Altitude']].map(([id,label]) => <option key={id} value={id}>{label}</option>)}</select></label>
    </div>
  </main>;
}

export function MapShortcut() {
  const { hasSelectedLocation, mapOpen, setMapOpen, setChatOpen } = usePlatform();
  if (!hasSelectedLocation || mapOpen) return null;
  return <Button size="icon" variant="outline" aria-label="Abrir mapa" title="Abrir mapa" onClick={() => {setChatOpen(false);setMapOpen(true);}} className="fixed bottom-[5.5rem] right-6 z-[1250] size-11 bg-card text-agriculture shadow-panel"><MapIcon/></Button>;
}