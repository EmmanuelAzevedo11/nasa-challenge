import { createFileRoute } from '@tanstack/react-router';
import { PlanningPage } from '@/components/PlanningPage';
import { pageHead } from '@/lib/metadata';
export const Route=createFileRoute('/plantio')({head:()=>pageHead('Planejamento de Plantio','Avalie culturas candidatas e compare alternativas agrícolas para sua propriedade em São Paulo.'),component:()=> <PlanningPage/>});
