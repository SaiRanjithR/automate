import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Navigate, useNavigate, useSearchParams } from 'react-router'
import { z } from 'zod'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useLogin, useMe } from '@/features/auth/api'
import { errorMessage } from '@/lib/api'

const schema = z.object({
  email: z.string().trim().email('Enter a valid email'),
  password: z.string().min(1, 'Enter your password'),
})
type LoginForm = z.infer<typeof schema>

export function LoginPage() {
  const { data: user } = useMe()
  const login = useLogin()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const next = params.get('next') ?? '/dashboard'
  const form = useForm<LoginForm>({
    resolver: zodResolver(schema),
    defaultValues: { email: '', password: '' },
  })

  if (user) return <Navigate to={next.startsWith('/') ? next : '/dashboard'} replace />

  const onSubmit = form.handleSubmit((values) => {
    login.mutate(values, {
      onSuccess: () => void navigate(next.startsWith('/') ? next : '/dashboard', { replace: true }),
    })
  })

  return (
    <div className="flex min-h-svh items-center justify-center bg-muted/40 p-6">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <div className="mb-2 flex items-center gap-2 text-base font-semibold">
            <span aria-hidden="true" className="size-6 rounded-md bg-primary" />
            BidReady
          </div>
          <CardTitle>Sign in</CardTitle>
          <CardDescription>RFP compliance matrix and auto-drafter</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={(event) => void onSubmit(event)}
            className="flex flex-col gap-4"
            noValidate
          >
            {login.error ? (
              <Alert variant="destructive">
                <AlertDescription>{errorMessage(login.error)}</AlertDescription>
              </Alert>
            ) : null}
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" autoComplete="username" {...form.register('email')} />
              {form.formState.errors.email ? (
                <p className="text-xs text-destructive">{form.formState.errors.email.message}</p>
              ) : null}
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                {...form.register('password')}
              />
              {form.formState.errors.password ? (
                <p className="text-xs text-destructive">{form.formState.errors.password.message}</p>
              ) : null}
            </div>
            <Button type="submit" disabled={login.isPending}>
              {login.isPending ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
