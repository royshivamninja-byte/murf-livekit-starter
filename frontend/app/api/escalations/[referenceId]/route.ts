import { NextRequest, NextResponse } from 'next/server';
import { placeResolutionCall } from '@/lib/outbound-call';

const BACKEND_URL =
  process.env.CATALOGUE_API_URL?.replace(/\/catalogue$/, '') ?? 'http://127.0.0.1:8001';

async function proxy(referenceId: string, init?: RequestInit) {
  try {
    const response = await fetch(`${BACKEND_URL}/escalations/${encodeURIComponent(referenceId)}`, {
      ...init,
      cache: 'no-store',
      signal: AbortSignal.timeout(2500),
    });
    return NextResponse.json(await response.json(), { status: response.status });
  } catch (error) {
    console.error('Escalation API unavailable', error);
    return NextResponse.json(
      { error: 'Human-help request is temporarily unavailable.' },
      { status: 503 }
    );
  }
}

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ referenceId: string }> }
) {
  const { referenceId } = await params;
  return proxy(referenceId);
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ referenceId: string }> }
) {
  const { referenceId } = await params;
  const requested = (await request.json()) as { status?: string };
  const currentResponse = await fetch(
    `${BACKEND_URL}/escalations/${encodeURIComponent(referenceId)}`,
    { cache: 'no-store' }
  );
  const current = currentResponse.ok
    ? ((await currentResponse.json()) as { status: string; customer_name: string })
    : null;
  const updatedResponse = await proxy(referenceId, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(requested),
  });
  if (
    updatedResponse.status !== 200 ||
    requested.status !== 'RESOLVED' ||
    current?.status === 'RESOLVED'
  ) {
    return updatedResponse;
  }

  const updated = await updatedResponse.json();
  try {
    const callback = await placeResolutionCall({
      customerName: current?.customer_name || 'Customer',
      referenceId,
      phoneNumber: '+918423896052',
    });
    return NextResponse.json({ ...updated, resolution_call: callback });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Resolution call failed';
    console.error(
      JSON.stringify({ event: 'resolution_call_failed', referenceId, reason: message })
    );
    return NextResponse.json({ ...updated, resolution_call: { state: 'FAILED', error: message } });
  }
}
