import { createFileRoute } from '@tanstack/react-router';
import { PlanningPage } from '@/components/PlanningPage';
import { pageHead } from '@/lib/metadata';
export const Route=createFileRoute('/rotacao')({head:()=>pageHead('Planejamento de Rotação','Explore estratégias de diversificação e sequências de cultivo para conservar o solo.'),component:()=> <PlanningPage rotation/>});
