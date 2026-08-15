'use client';

import { HeadphonesIcon, MicIcon, PackageIcon, RotateCcwIcon, ShoppingBagIcon } from 'lucide-react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { useVoiceAssistant } from '@livekit/components-react';
import { AgentAudioVisualizerRadial } from '@/components/agents-ui/agent-audio-visualizer-radial';
import { cn } from '@/lib/shadcn/utils';

export type MitraVisualState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'handoff' | 'error';

interface MitraVoiceCoreProps {
  state: MitraVisualState;
  specialistName?: string | null;
  handoffName?: string | null;
  compact?: boolean;
  className?: string;
}

const stateDetails: Record<
  Exclude<MitraVisualState, 'handoff'>,
  { label: string; description: string; tone: string }
> = {
  idle: { label: 'Ready', description: 'Mitra is ready', tone: 'bg-orange-500' },
  listening: { label: 'Listening…', description: 'Listening to you', tone: 'bg-emerald-500' },
  thinking: { label: 'Thinking…', description: 'Working on your request', tone: 'bg-amber-500' },
  speaking: { label: 'Speaking…', description: 'Mitra is responding', tone: 'bg-orange-500' },
  error: { label: 'Needs attention', description: 'The voice session has an error', tone: 'bg-red-500' },
};

function specialistIcon(name: string) {
  if (name.includes('Product')) return <ShoppingBagIcon aria-hidden="true" />;
  if (name.includes('Order')) return <PackageIcon aria-hidden="true" />;
  return <RotateCcwIcon aria-hidden="true" />;
}

export function MitraVoiceCore({
  state,
  specialistName,
  handoffName,
  compact = false,
  className,
}: MitraVoiceCoreProps) {
  const reduceMotion = useReducedMotion();
  const { state: liveKitState, audioTrack } = useVoiceAssistant();
  const visibleState = state === 'handoff' ? 'thinking' : state;
  const details = stateDetails[visibleState];
  const activeName = specialistName || 'Mitra';

  return (
    <div
      className={cn('relative flex flex-col items-center justify-center', compact ? 'scale-[.72]' : '', className)}
      data-voice-state={state}
      aria-label={`${activeName}. ${details.description}`}
    >
      <div className="mitra-core-stage relative grid size-[250px] place-items-center sm:size-[310px]">
        <AgentAudioVisualizerRadial
          state={liveKitState}
          audioTrack={audioTrack}
          size="xl"
          radius={compact ? 66 : 94}
          barCount={32}
          color={state === 'listening' ? '#059669' : '#f97316'}
          className="absolute inset-0 size-full opacity-75"
        />

        <div className="mitra-core-ring mitra-core-ring-outer absolute size-[78%] rounded-full" />
        <div className="mitra-core-ring mitra-core-ring-inner absolute size-[61%] rounded-full" />

        {state === 'thinking' && (
          <div className="mitra-core-orbit absolute size-[70%] rounded-full" aria-hidden="true">
            <span /><span /><span />
          </div>
        )}

        <motion.div
          animate={
            reduceMotion
              ? undefined
              : state === 'speaking'
                ? { scale: [1, 1.055, 0.985, 1.035, 1] }
                : state === 'listening'
                  ? { scale: [1, 1.035, 1] }
                  : { y: [0, -4, 0], scale: [1, 1.012, 1] }
          }
          transition={{ duration: state === 'speaking' ? 1.15 : 3.8, repeat: Infinity, ease: 'easeInOut' }}
          className="mitra-core-orb relative z-10 grid size-[42%] place-items-center rounded-full"
        >
          <div className="absolute inset-[10%] rounded-full border border-white/40" />
          <div className="relative text-center text-white drop-shadow-sm">
            {state === 'listening' ? (
              <MicIcon className="mx-auto mb-1 size-6" aria-hidden="true" />
            ) : (
              <HeadphonesIcon className="mx-auto mb-1 size-6" aria-hidden="true" />
            )}
            <span className="block font-mono text-[10px] font-bold tracking-[.22em]">MITRA</span>
            <span className="block text-[8px] font-semibold tracking-[.16em] text-orange-50/80">AI CORE</span>
          </div>
        </motion.div>

        <AnimatePresence>
          {state === 'handoff' && handoffName && (
            <motion.div
              initial={{ opacity: 0, scale: 0.92 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 1.04 }}
              transition={{ duration: reduceMotion ? 0 : 0.24 }}
              className="absolute inset-2 z-30 flex flex-col items-center justify-center rounded-full border border-orange-200/80 bg-white/94 p-6 text-center shadow-2xl backdrop-blur dark:border-orange-800 dark:bg-stone-950/94"
              role="status"
              aria-live="polite"
            >
              <motion.div
                animate={reduceMotion ? undefined : { rotate: 360 }}
                transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}
                className="grid size-11 place-items-center rounded-full bg-orange-100 text-orange-700 dark:bg-orange-950 dark:text-orange-300"
              >
                <RotateCcwIcon className="size-5" aria-hidden="true" />
              </motion.div>
              <p className="mt-4 font-mono text-[10px] font-bold tracking-[.2em] text-orange-700 uppercase">Handoff</p>
              <p className="mt-1 max-w-48 text-sm font-bold">Connecting to {handoffName}…</p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={`${state}-${details.label}`}
          initial={{ opacity: 0, y: 5 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -5 }}
          className="-mt-3 flex items-center gap-2 rounded-full border border-stone-200/80 bg-white/85 px-3 py-1.5 text-sm font-semibold shadow-sm backdrop-blur dark:border-stone-700 dark:bg-stone-900/85"
          role="status"
          aria-live="polite"
        >
          <span className={cn('size-2 rounded-full', details.tone, state === 'speaking' && 'animate-pulse')} />
          {state === 'handoff' ? 'Connecting to specialist' : details.label}
        </motion.div>
      </AnimatePresence>

      <AnimatePresence mode="wait">
        <motion.div
          key={activeName}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -5 }}
          className={cn(
            'mt-3 flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-bold shadow-sm',
            specialistName
              ? 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200'
              : 'border-orange-200 bg-orange-50 text-orange-800 dark:border-orange-900 dark:bg-orange-950 dark:text-orange-200'
          )}
        >
          <span className="[&>svg]:size-4">{specialistName ? specialistIcon(specialistName) : <HeadphonesIcon aria-hidden="true" />}</span>
          <span>{activeName}</span>
          <span className="font-normal opacity-70">{specialistName ? 'Specialist' : 'Main Assistant'}</span>
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
