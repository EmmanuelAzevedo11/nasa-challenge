import { createFileRoute } from '@tanstack/react-router';
import { PlanningPage } from '@/components/PlanningPage';
import { pageHead } from '@/lib/metadata';
import { usePlatform } from '@/components/PlatformContext';

export const Route = createFileRoute('/')({
  head: () => pageHead('Sua propriedade no mapa', 'Selecione sua propriedade no mapa de São Paulo para iniciar o planejamento agrícola no AgroSat SP.'),
  component: EntryPage,
});

export function EntryPage() {
  const { hasSelectedLocation } = usePlatform();
  return hasSelectedLocation ? <PlanningPage/> : null;
}