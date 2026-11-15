import { createFileRoute, redirect } from '@tanstack/react-router';
import { pageHead } from '@/lib/metadata';
export const Route=createFileRoute('/mapa')({head:()=>pageHead('Mapa e diagnóstico agroambiental','Explore São Paulo e consulte indicadores ambientais para apoiar o planejamento agrícola.'),beforeLoad:()=>{throw redirect({to:'/',replace:true});}});