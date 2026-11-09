import { describe, expect, it, vi } from 'vitest'

import { HttpUsersGateway } from '@/features/users/infrastructure/http-users-gateway'
import { InvalidResponseError } from '@/shared/http/errors'
import { HttpClient } from '@/shared/http/http-client'

import { HttpManualsGateway } from './http-manuals-gateway'

const apiManual = {
  id: 'm1',
  title: 'Compressor',
  file_name: 'cx500.pdf',
  status: 'failed',
  page_count: null,
  chunk_count: null,
  figure_count: null,
  describing_figures: false,
  figures_described: 0,
  figures_error: null,
  failure_reason: 'PDF protegido por senha',
  created_at: '2026-10-07T10:00:00Z',
}

const apiUser = {
  id: 'u1',
  username: 'maria',
  display_name: 'Maria',
  role: 'user',
  auth_source: 'local',
  is_active: true,
  must_change_password: true,
  last_login_at: null,
  created_at: '2026-10-07T10:00:00Z',
}

function client(body: unknown) {
  const fetchFn = vi
    .fn<typeof fetch>()
    .mockImplementation(() => Promise.resolve(Response.json(body)))
  return { http: new HttpClient('http://api', { fetchFn }), fetchFn }
}

describe('HttpManualsGateway', () => {
  it('maps the manual list', async () => {
    const { http } = client([apiManual])

    const [manual] = await new HttpManualsGateway(http).list()

    expect(manual).toEqual({
      id: 'm1',
      title: 'Compressor',
      fileName: 'cx500.pdf',
      status: 'failed',
      pageCount: null,
      chunkCount: null,
      figureCount: null,
      describingFigures: false,
      figuresDescribed: 0,
      figuresError: null,
      failureReason: 'PDF protegido por senha',
      createdAt: new Date('2026-10-07T10:00:00Z'),
    })
  })

  it('uploads the file as multipart and calls the right routes', async () => {
    const { http, fetchFn } = client(apiManual)
    const gateway = new HttpManualsGateway(http)

    await gateway.upload(new File(['%PDF'], 'cx500.pdf'))
    await gateway.reindex('m1')
    await gateway.remove('m1')

    const calls = fetchFn.mock.calls.map(([url, init]) => [init?.method, url])
    expect(calls).toEqual([
      ['POST', 'http://api/api/v1/manuals'],
      ['POST', 'http://api/api/v1/manuals/m1/reindex'],
      ['DELETE', 'http://api/api/v1/manuals/m1'],
    ])
    const form = fetchFn.mock.calls[0]?.[1]?.body
    expect(form).toBeInstanceOf(FormData)
    expect((form as FormData).get('file')).toBeInstanceOf(File)
    expect(gateway.fileUrl('m 1')).toBe('http://api/api/v1/manuals/m%201/file')
  })

  it('sends the figure option only when asked and calls the figure routes', async () => {
    const fetchFn = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(Response.json(apiManual))
      .mockResolvedValueOnce(Response.json(apiManual))
      .mockResolvedValueOnce(Response.json({ with_figures: 4, pending: 3 }))
      .mockResolvedValueOnce(Response.json({ ...apiManual, describing_figures: true }))
    const gateway = new HttpManualsGateway(new HttpClient('http://api', { fetchFn }))

    await gateway.upload(new File(['%PDF'], 'cx500.pdf'), { describeFigures: true })
    await gateway.reindex('m1', { describeFigures: true })
    const plan = await gateway.figurePlan('m1')
    const describing = await gateway.describeFigures('m1')

    const calls = fetchFn.mock.calls.map(([url, init]) => [init?.method, url])
    expect(calls).toEqual([
      ['POST', 'http://api/api/v1/manuals'],
      ['POST', 'http://api/api/v1/manuals/m1/reindex?describe_figures=true'],
      ['GET', 'http://api/api/v1/manuals/m1/figures'],
      ['POST', 'http://api/api/v1/manuals/m1/figures'],
    ])
    const form = fetchFn.mock.calls[0]?.[1]?.body as FormData
    expect(form.get('describe_figures')).toBe('true')
    expect(plan).toEqual({ withFigures: 4, pending: 3 })
    expect(describing.describingFigures).toBe(true)
  })

  it('rejects unexpected payloads', async () => {
    await expect(new HttpManualsGateway(client({}).http).list()).rejects.toBeInstanceOf(
      InvalidResponseError,
    )
    await expect(new HttpManualsGateway(client([{ id: 1 }]).http).list()).rejects.toBeInstanceOf(
      InvalidResponseError,
    )
  })

  it('reads and saves the daily sync schedule', async () => {
    const { http, fetchFn } = client({
      enabled: true,
      time: '06:30',
      describe_figures: true,
      timezone: 'America/Sao_Paulo',
      next_run_at: '2026-11-06T09:30:00Z',
      last_triggered_at: null,
      last_trigger_error: null,
      updated_at: '2026-11-05T13:00:00Z',
      updated_by: 'Ana Admin',
    })

    const schedule = await new HttpManualsGateway(http).updateSyncSchedule({
      enabled: true,
      time: '06:30',
      describeFigures: true,
    })

    expect(fetchFn).toHaveBeenCalledWith(
      'http://api/api/v1/sync/schedule',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ enabled: true, time: '06:30', describe_figures: true }),
      }),
    )
    expect(schedule).toMatchObject({
      enabled: true,
      time: '06:30',
      describeFigures: true,
      nextRunAt: new Date('2026-11-06T09:30:00Z'),
      lastTriggeredAt: null,
      updatedBy: 'Ana Admin',
    })
  })
})

describe('HttpManualsGateway sync', () => {
  const apiRun = {
    started_at: '2026-10-16T10:00:00Z',
    started_by: 'Ana',
    finished_at: null,
    running: true,
    total: 3,
    describe_figures: true,
    done: 1,
    succeeded: 1,
    failures: [{ action: 'add', file_name: 'ruim.pdf', detail: 'não é um PDF' }],
    error: null,
  }

  it('maps the status, the check and the start', async () => {
    const fetchFn = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(Response.json({ enabled: true, running: true, last_run: apiRun }))
      .mockResolvedValueOnce(
        Response.json({
          counts: { add: 1, update: 0, retitle: 0, remove: 0, unchanged: 2, ignore: 0, figures: 0 },
          to_index: 1,
          items: [{ action: 'add', file_name: 'a.pdf', title: 'A', reason: null }],
        }),
      )
      .mockResolvedValueOnce(Response.json(apiRun))
    const gateway = new HttpManualsGateway(new HttpClient('http://api', { fetchFn }))

    const status = await gateway.syncStatus()
    const check = await gateway.checkSync()
    const run = await gateway.startSync({ describeFigures: true })

    expect(status.lastRun).toMatchObject({
      startedAt: new Date('2026-10-16T10:00:00Z'),
      finishedAt: null,
      failures: [{ action: 'add', fileName: 'ruim.pdf', detail: 'não é um PDF' }],
    })
    expect(check).toMatchObject({ toIndex: 1, items: [{ fileName: 'a.pdf' }] })
    expect(run).toMatchObject({ done: 1, describeFigures: true })
    const calls = fetchFn.mock.calls.map(([url, init]) => [init?.method, url])
    expect(calls).toEqual([
      ['GET', 'http://api/api/v1/sync'],
      ['POST', 'http://api/api/v1/sync/check'],
      ['POST', 'http://api/api/v1/sync/run?describe_figures=true'],
    ])
  })

  it('rejects unexpected payloads', async () => {
    await expect(new HttpManualsGateway(client({}).http).syncStatus()).rejects.toBeInstanceOf(
      InvalidResponseError,
    )
  })
})

describe('HttpUsersGateway', () => {
  it('maps users and sends changes in the API format', async () => {
    const { http, fetchFn } = client(apiUser)
    const gateway = new HttpUsersGateway(http)

    const created = await gateway.create({
      username: 'maria',
      displayName: 'Maria',
      role: 'user',
      temporaryPassword: 'abcd-efgh-jkmn',
    })
    await gateway.resetPassword('u1', 'nova-prov-123')
    await gateway.update('u1', { isActive: false })

    expect(created).toMatchObject({
      displayName: 'Maria',
      mustChangePassword: true,
      lastLoginAt: null,
    })
    const bodies = fetchFn.mock.calls.map(([, init]) => init?.body)
    expect(bodies).toEqual([
      '{"username":"maria","display_name":"Maria","role":"user","temporary_password":"abcd-efgh-jkmn"}',
      '{"temporary_password":"nova-prov-123"}',
      '{"is_active":false}',
    ])
  })

  it('lists users and parses the last login date', async () => {
    const { http } = client([{ ...apiUser, last_login_at: '2026-10-07T12:00:00Z' }])

    const [user] = await new HttpUsersGateway(http).list()

    expect(user?.lastLoginAt).toEqual(new Date('2026-10-07T12:00:00Z'))
  })
})
