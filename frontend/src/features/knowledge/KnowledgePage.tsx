import { BookOpen, Search, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Dropzone } from '@/components/common/Dropzone'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { LoadingRows } from '@/components/common/LoadingRows'
import { PageHeader } from '@/components/common/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  useDeleteKnowledge,
  useKnowledge,
  useUpdateKnowledge,
  useKnowledgeSearch,
  useUploadKnowledge,
} from '@/features/company/api'
import { errorMessage } from '@/lib/api'

const DOC_TYPES = [
  { value: 'past_proposal', label: 'Past proposal' },
  { value: 'case_study', label: 'Case study' },
  { value: 'profile', label: 'Company profile' },
  { value: 'product', label: 'Product sheet' },
  { value: 'certificate', label: 'Certificate' },
  { value: 'other', label: 'Other' },
]
const TYPE_LABEL = Object.fromEntries(DOC_TYPES.map((t) => [t.value, t.label]))
const OUTCOMES = [
  { value: 'won', label: 'Won bid' },
  { value: 'lost', label: 'Lost bid' },
  { value: 'unknown', label: 'Not known' },
]

export function KnowledgePage() {
  const [docType, setDocType] = useState('past_proposal')
  const [outcome, setOutcome] = useState('unknown')
  const [query, setQuery] = useState('')
  const [submitted, setSubmitted] = useState('')
  const docsQuery = useKnowledge(false)
  const indexing = (docsQuery.data ?? []).some(
    (d) => d.status === 'pending' || d.status === 'indexing',
  )
  const docs = useKnowledge(indexing)
  const upload = useUploadKnowledge()
  const remove = useDeleteKnowledge()
  const updateDoc = useUpdateKnowledge()
  const search = useKnowledgeSearch(submitted)

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Knowledge base"
        description="Past proposals, case studies, product sheets and certificates. Every drafted answer cites these files."
      />
      <Card>
        <CardHeader>
          <CardTitle>Add documents</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-wrap gap-4">
            <div className="flex w-56 flex-col gap-1.5">
              <Label htmlFor="doc-type">Document type</Label>
              <Select value={docType} onValueChange={setDocType}>
                <SelectTrigger id="doc-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DOC_TYPES.map((t) => (
                    <SelectItem key={t.value} value={t.value}>
                      {t.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex w-56 flex-col gap-1.5">
              <Label htmlFor="doc-outcome">Bid outcome</Label>
              <Select value={outcome} onValueChange={setOutcome}>
                <SelectTrigger id="doc-outcome">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {OUTCOMES.map((o) => (
                    <SelectItem key={o.value} value={o.value}>
                      {o.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            Mark past proposals as won or lost. Evidence from won bids is preferred when drafting.
          </p>
          <Dropzone
            label={upload.isPending ? 'Uploading…' : 'Drop files here or click to upload'}
            multiple
            disabled={upload.isPending}
            onFiles={(files) =>
              upload.mutate(
                { files, docType, outcome },
                {
                  onSuccess: () => toast.success(`Indexing ${files.length} file(s)`),
                  onError: (e) => toast.error(errorMessage(e)),
                },
              )
            }
          />
        </CardContent>
      </Card>

      {docs.isPending ? (
        <LoadingRows rows={3} />
      ) : docs.error ? (
        <ErrorState message={errorMessage(docs.error)} onRetry={() => void docs.refetch()} />
      ) : docs.data.length === 0 ? (
        <EmptyState
          icon={BookOpen}
          title="No documents yet"
          description="Without documents every requirement becomes a gap. Upload at least one past proposal or company profile."
        />
      ) : (
        <Card>
          <CardContent className="px-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="pl-6">File</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Outcome</TableHead>
                  <TableHead>Pages</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-12" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {docs.data.map((doc) => (
                  <TableRow key={doc.id}>
                    <TableCell className="pl-6 font-medium">{doc.filename}</TableCell>
                    <TableCell>{TYPE_LABEL[doc.doc_type] ?? doc.doc_type}</TableCell>
                    <TableCell>
                      <Select
                        value={doc.outcome}
                        onValueChange={(value) =>
                          updateDoc.mutate(
                            { id: doc.id, outcome: value },
                            { onSuccess: () => toast.success('Outcome saved') },
                          )
                        }
                      >
                        <SelectTrigger
                          size="sm"
                          aria-label={`Outcome for ${doc.filename}`}
                          className="w-32"
                        >
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {OUTCOMES.map((o) => (
                            <SelectItem key={o.value} value={o.value}>
                              {o.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </TableCell>
                    <TableCell className="tabular-nums">{doc.pages || '—'}</TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          doc.status === 'failed'
                            ? 'destructive'
                            : doc.status === 'ready'
                              ? 'secondary'
                              : 'outline'
                        }
                      >
                        {doc.status === 'ready'
                          ? 'Ready'
                          : doc.status === 'failed'
                            ? 'Failed'
                            : 'Indexing…'}
                      </Badge>
                      {doc.error ? (
                        <p className="mt-1 text-xs text-destructive">{doc.error}</p>
                      ) : null}
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={`Delete ${doc.filename}`}
                        onClick={() =>
                          remove.mutate(doc.id, {
                            onSuccess: () => toast.success('Document removed'),
                          })
                        }
                      >
                        <Trash2 />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Test retrieval</CardTitle>
          <CardDescription>
            See which passages the drafter would cite for a requirement.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <form
            className="flex gap-2"
            onSubmit={(event) => {
              event.preventDefault()
              setSubmitted(query)
            }}
          >
            <Input
              aria-label="Search the knowledge base"
              placeholder="e.g. ABDM certification, 24x7 helpdesk"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
            <Button type="submit" variant="outline">
              <Search aria-hidden="true" /> Search
            </Button>
          </form>
          {search.isFetching ? <LoadingRows rows={2} /> : null}
          {search.data?.length === 0 ? (
            <p className="text-sm text-muted-foreground">No passages found.</p>
          ) : null}
          <ul className="flex flex-col gap-3">
            {search.data?.map((hit) => (
              <li key={hit.chunk_id} className="rounded-md border border-border p-3">
                <p className="mb-1 text-xs text-muted-foreground">
                  {hit.filename} · page {hit.page} · score {hit.score.toFixed(2)}
                </p>
                <p className="font-serif text-sm">{hit.text}</p>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  )
}
