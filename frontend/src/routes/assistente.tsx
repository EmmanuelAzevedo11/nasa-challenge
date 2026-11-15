import { createFileRoute } from '@tanstack/react-router';
import { ChatConversation } from '@/components/ChatWidget';
import { PageTitle } from '@/components/PlatformHeader';
import { pageHead } from '@/lib/metadata';
export const Route=createFileRoute('/assistente')({head:()=>pageHead('AgroSat IA','Converse sobre clima, plantio e rotação com contexto da localização selecionada.'),component:()=> <main className="mx-auto flex h-[calc(100dvh-100px)] min-h-[560px] w-full max-w-4xl flex-col p-4 md:p-7"><PageTitle title="AgroSat IA" subtitle="Interpretação orientativa das condições ambientais e do planejamento agrícola."/><section className="flex min-h-0 flex-1 flex-col border-y border-border"><ChatConversation/></section></main>});
