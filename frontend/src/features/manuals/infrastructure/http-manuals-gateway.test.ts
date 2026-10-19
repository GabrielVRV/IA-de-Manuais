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

  it('rejects unexpected payloads', async () => {
    await expect(new HttpManualsGateway(client({}).http).list()).rejects.toBeInstanceOf(
      InvalidResponseError,
    )
    await expect(new HttpManualsGateway(client([{ id: 1 }]).http).list()).rejects.toBeInstanceOf(
      InvalidResponseError,
    )
  })
})

describe('HttpManualsGateway sync', () => {
  const apiRun = {
    started_at: '2026-10-16T10:00:00Z',
    started_by: 'Ana',
    finished_at: null,
    running: true,
    total: 3,
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
          counts: { add: 1, update: 0, retitle: 0, remove: 0, unchanged: 2, ignore: 0 },
          to_index: 1,
          items: [{ action: 'add', file_name: 'a.pdf', title: 'A', reason: null }],
        }),
      )
      .mockResolvedValueOnce(Response.json(apiRun))
    const gateway = new HttpManualsGateway(new HttpClient('http://api', { fetchFn }))

    const status = await gateway.syncStatus()
    const check = await gateway.checkSync()
    const run = await gateway.startSync()

    expect(status.lastRun).toMatchObject({
      startedAt: new Date('2026-10-16T10:00:00Z'),
      finishedAt: null,
      failures: [{ action: 'add', fileName: 'ruim.pdf', detail: 'não é um PDF' }],
    })
    expect(check).toMatchObject({ toIndex: 1, items: [{ fileName: 'a.pdf' }] })
    expect(run.done).toBe(1)
    const calls = fetchFn.mock.calls.map(([url, init]) => [init?.method, url])
    expect(calls).toEqual([
      ['GET', 'http://api/api/v1/sync'],
      ['POST', 'http://api/api/v1/sync/check'],
      ['POST', 'http://api/api/v1/sync/run'],
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
