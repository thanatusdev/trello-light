import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Link, useLocation } from 'react-router'
import { z } from 'zod'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Field, FieldError, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'

import { loginErrorMessage } from './auth-errors'
import { useLogin } from './use-session'

const loginSchema = z.object({
  email: z.email('Enter a valid email address.'),
  password: z.string().min(1, 'Enter your password.'),
})

type LoginValues = z.infer<typeof loginSchema>

export function LoginPage() {
  const location = useLocation()
  const loginMutation = useLogin()
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '' },
  })

  // On success the store gets the tokens and PublicOnlyRoute redirects.
  const onSubmit = handleSubmit((values) => {
    loginMutation.mutate(values)
  })

  return (
    <main className="flex min-h-svh items-center justify-center bg-muted/40 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>
            <h1>Sign in</h1>
          </CardTitle>
          <CardDescription>Use your account to open the board.</CardDescription>
        </CardHeader>
        <CardContent>
          <form noValidate onSubmit={(event) => void onSubmit(event)}>
            <FieldGroup>
              {loginMutation.isError && (
                <Alert variant="destructive">
                  <AlertDescription>{loginErrorMessage(loginMutation.error)}</AlertDescription>
                </Alert>
              )}
              <Field data-invalid={errors.email ? true : undefined}>
                <FieldLabel htmlFor="email">Email</FieldLabel>
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  aria-invalid={errors.email ? true : undefined}
                  {...register('email')}
                />
                <FieldError errors={[errors.email]} />
              </Field>
              <Field data-invalid={errors.password ? true : undefined}>
                <FieldLabel htmlFor="password">Password</FieldLabel>
                <Input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  aria-invalid={errors.password ? true : undefined}
                  {...register('password')}
                />
                <FieldError errors={[errors.password]} />
              </Field>
              <Button type="submit" className="w-full" disabled={loginMutation.isPending}>
                {loginMutation.isPending ? 'Signing in…' : 'Sign in'}
              </Button>
              <p className="text-center text-sm text-muted-foreground">
                New here? {/* Keep `state` so a post-sign-in redirect survives switching pages. */}
                <Link
                  to="/register"
                  state={location.state as unknown}
                  className="text-foreground underline underline-offset-4 hover:text-primary"
                >
                  Create an account
                </Link>
              </p>
              {import.meta.env.DEV && (
                <p className="text-center text-xs text-muted-foreground">
                  Demo: alice@example.com / Demo1234!
                </p>
              )}
            </FieldGroup>
          </form>
        </CardContent>
      </Card>
    </main>
  )
}
