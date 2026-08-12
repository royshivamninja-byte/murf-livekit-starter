import { NextResponse } from 'next/server';

const BACKEND_URL =
  process.env.CATALOGUE_API_URL?.replace(/\/catalogue$/, '') ?? 'http://127.0.0.1:8001';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const response = await fetch(`${BACKEND_URL}/escalations`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(2500),
    });
    const payload = await response.json();
    return NextResponse.json(payload, { status: response.status });
  } catch (error) {
    console.error('Escalation API unavailable', error);
    return NextResponse.json(
      { error: 'Human-help requests are temporarily unavailable.' },
      { status: 503 }
    );
  }
}
