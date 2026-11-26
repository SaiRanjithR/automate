import { zodResolver } from '@hookform/resolvers/zod'
import { Plus, Trash2 } from 'lucide-react'
import { useEffect } from 'react'
import { useFieldArray, useForm, type FieldErrors, type UseFormRegister } from 'react-hook-form'
import { toast } from 'sonner'
import { z } from 'zod'

import { ErrorState } from '@/components/common/ErrorState'
import { LoadingRows } from '@/components/common/LoadingRows'
import { PageHeader } from '@/components/common/PageHeader'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useCompany, useSaveCompany, type Company } from '@/features/company/api'
import { errorMessage } from '@/lib/api'

const optionalPattern = (pattern: RegExp, message: string) =>
  z
    .string()
    .trim()
    .transform((value) => value.toUpperCase())
    .refine((value) => value === '' || pattern.test(value), message)

const schema = z.object({
  legal_name: z.string().trim().min(2, 'Enter the legal name'),
  short_name: z.string().trim(),
  address: z.string().trim(),
  gstin: optionalPattern(
    /^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/,
    'GSTIN must be 15 characters, e.g. 29ABCDE1234F1Z5',
  ),
  pan: optionalPattern(/^[A-Z]{5}\d{4}[A-Z]$/, 'PAN must be 10 characters, e.g. ABCDE1234F'),
  udyam_no: z.string().trim(),
  signatory_name: z.string().trim(),
  signatory_designation: z.string().trim(),
  email: z.string().trim(),
  phone: z.string().trim(),
  website: z.string().trim(),
  year_established: z
    .union([z.coerce.number().int().min(1800).max(2100), z.literal('').transform(() => null)])
    .nullable(),
  turnover: z.array(
    z.object({ fy: z.string().trim().min(4, 'Year'), crore: z.coerce.number().min(0) }),
  ),
  certifications: z.array(
    z.object({
      name: z.string().trim().min(2, 'Name'),
      number: z.string().trim(),
      valid_until: z.string().trim(),
    }),
  ),
  style_sample: z.string(),
})
type FormInput = z.input<typeof schema>
type FormOutput = z.output<typeof schema>

function toForm(company: Company): FormInput {
  return {
    legal_name: company.legal_name ?? '',
    short_name: company.short_name ?? '',
    address: company.address ?? '',
    gstin: company.gstin ?? '',
    pan: company.pan ?? '',
    udyam_no: company.udyam_no ?? '',
    signatory_name: company.signatory_name ?? '',
    signatory_designation: company.signatory_designation ?? '',
    email: company.email ?? '',
    phone: company.phone ?? '',
    website: company.website ?? '',
    year_established: company.year_established ?? '',
    turnover: (company.turnover ?? []).map((t) => ({ fy: t.fy, crore: t.amount_inr / 1e7 })),
    certifications: (company.certifications ?? []).map((c) => ({
      name: c.name,
      number: c.number ?? '',
      valid_until: c.valid_until ?? '',
    })),
    style_sample: company.style_sample ?? '',
  }
}

type FieldProps = {
  name: Exclude<keyof FormInput, 'turnover' | 'certifications'>
  label: string
  register: UseFormRegister<FormInput>
  errors: FieldErrors<FormInput>
  placeholder?: string
}

function Field({ name, label, register, errors, placeholder }: FieldProps) {
  const error = errors[name]
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={name}>{label}</Label>
      <Input
        id={name}
        placeholder={placeholder}
        aria-invalid={Boolean(error)}
        {...register(name)}
      />
      {error?.message ? <p className="text-xs text-destructive">{String(error.message)}</p> : null}
    </div>
  )
}

export function CompanyPage() {
  const { data, isPending, error, refetch } = useCompany()
  const save = useSaveCompany()
  const form = useForm<FormInput, unknown, FormOutput>({ resolver: zodResolver(schema) })
  const turnover = useFieldArray({ control: form.control, name: 'turnover' })
  const certifications = useFieldArray({ control: form.control, name: 'certifications' })
  const { register, formState } = form

  useEffect(() => {
    if (data) form.reset(toForm(data))
  }, [data, form])

  const onSubmit = form.handleSubmit((values) => {
    save.mutate(
      {
        ...values,
        turnover: values.turnover.map((t) => ({ fy: t.fy, amount_inr: Math.round(t.crore * 1e7) })),
      },
      {
        onSuccess: () => toast.success('Company profile saved'),
        onError: (e) => toast.error(errorMessage(e)),
      },
    )
  })

  if (isPending) return <LoadingRows rows={6} />
  if (error) return <ErrorState message={errorMessage(error)} onRetry={() => void refetch()} />

  return (
    <form onSubmit={(event) => void onSubmit(event)} className="flex flex-col gap-6" noValidate>
      <PageHeader
        title="Company profile"
        description="Fill once. BidReady uses these details in every covering letter, form and eligibility check."
        action={
          <Button type="submit" disabled={save.isPending}>
            {save.isPending ? 'Saving…' : 'Save'}
          </Button>
        }
      />
      <Card>
        <CardHeader>
          <CardTitle>Legal details</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <Field
            name="legal_name"
            label="Legal name"
            register={register}
            errors={formState.errors}
          />
          <Field
            name="short_name"
            label="Short name (used in file names)"
            register={register}
            errors={formState.errors}
          />
          <div className="md:col-span-2">
            <Field
              name="address"
              label="Registered address"
              register={register}
              errors={formState.errors}
            />
          </div>
          <Field
            name="gstin"
            label="GSTIN"
            register={register}
            errors={formState.errors}
            placeholder="29ABCDE1234F1Z5"
          />
          <Field
            name="pan"
            label="PAN"
            register={register}
            errors={formState.errors}
            placeholder="ABCDE1234F"
          />
          <Field
            name="udyam_no"
            label="Udyam registration"
            register={register}
            errors={formState.errors}
          />
          <Field
            name="year_established"
            label="Year established"
            register={register}
            errors={formState.errors}
          />
          <Field name="email" label="Email" register={register} errors={formState.errors} />
          <Field name="phone" label="Phone" register={register} errors={formState.errors} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Authorised signatory</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <Field name="signatory_name" label="Name" register={register} errors={formState.errors} />
          <Field
            name="signatory_designation"
            label="Designation"
            register={register}
            errors={formState.errors}
          />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Annual turnover</CardTitle>
          <CardDescription>
            Used for turnover eligibility checks. Amounts in INR crore.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {turnover.fields.map((field, index) => (
            <div key={field.id} className="flex items-end gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor={`fy-${index}`}>Financial year</Label>
                <Input
                  id={`fy-${index}`}
                  placeholder="2025-26"
                  {...register(`turnover.${index}.fy`)}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor={`crore-${index}`}>Turnover (INR crore)</Label>
                <Input
                  id={`crore-${index}`}
                  type="number"
                  step="0.01"
                  {...register(`turnover.${index}.crore`)}
                />
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label="Remove year"
                onClick={() => turnover.remove(index)}
              >
                <Trash2 />
              </Button>
            </div>
          ))}
          <Button
            type="button"
            variant="outline"
            className="self-start"
            onClick={() => turnover.append({ fy: '', crore: 0 })}
          >
            <Plus aria-hidden="true" /> Add year
          </Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Certifications</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {certifications.fields.map((field, index) => (
            <div key={field.id} className="grid items-end gap-3 md:grid-cols-[2fr_1.5fr_1fr_auto]">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor={`cert-${index}`}>Certification</Label>
                <Input
                  id={`cert-${index}`}
                  placeholder="ISO 27001:2022"
                  {...register(`certifications.${index}.name`)}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor={`certno-${index}`}>Number</Label>
                <Input id={`certno-${index}`} {...register(`certifications.${index}.number`)} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor={`valid-${index}`}>Valid until</Label>
                <Input
                  id={`valid-${index}`}
                  type="date"
                  {...register(`certifications.${index}.valid_until`)}
                />
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label="Remove certification"
                onClick={() => certifications.remove(index)}
              >
                <Trash2 />
              </Button>
            </div>
          ))}
          <Button
            type="button"
            variant="outline"
            className="self-start"
            onClick={() => certifications.append({ name: '', number: '', valid_until: '' })}
          >
            <Plus aria-hidden="true" /> Add certification
          </Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Writing style sample (optional)</CardTitle>
          <CardDescription>
            A paragraph from a past proposal so drafts sound like your company.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Textarea aria-label="Writing style sample" rows={4} {...register('style_sample')} />
        </CardContent>
      </Card>
    </form>
  )
}
