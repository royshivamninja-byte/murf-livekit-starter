import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL =
  process.env.CATALOGUE_API_URL?.replace(/\/catalogue$/, '') ?? 'http://127.0.0.1:8001';
const ENDPOINTS = new Set(['summary', 'calls', 'trends', 'failures']);

export const dynamic = 'force-dynamic';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ endpoint: string }> }
) {
  const { endpoint } = await params;
  if (!ENDPOINTS.has(endpoint)) {
    return NextResponse.json({ error: 'Analytics endpoint not found.' }, { status: 404 });
  }
  try {
    const query = request.nextUrl.searchParams.toString();
    const response = await fetch(
      `${BACKEND_URL}/analytics/${endpoint}${query ? `?${query}` : ''}`,
      {
        cache: 'no-store',
        signal: AbortSignal.timeout(3000),
      }
    );
    return NextResponse.json(await response.json(), { status: response.status });
  } catch (error) {
    console.error('Analytics API unavailable', error);
    return NextResponse.json(
      { error: 'Call analytics are temporarily unavailable.' },
      { status: 503 }
    );
  }
}
