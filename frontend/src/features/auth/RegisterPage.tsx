import { zodResolver } from '@hookform/resolvers/zod'
import { type FieldError as FormFieldError, useForm } from 'react-hook-form'
import { Link, useLocation } from 'react-router'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'

import { registerErrorMessage } from './auth-errors'
import {
  PASSWORD_MIN_LENGTH,
  type RegisterData,
  registerSchema,
  type RegisterValues,
} from './register-schema'
import { useRegister } from './use-session'

/** Accessibility wiring for an input: invalid state plus its hint and error, if any. */
function describe(id: string, error: FormFieldError | undefined, hint = false) {
  const ids = [hint && `${id}-hint`, error && `${id}-error`].filter(Boolean).join(' ')
  return {
    id,
    'aria-invalid': error ? true : undefined,
    'aria-describedby': ids || undefined,
  } as const
}

export function RegisterPage() {
  const location = useLocation()
  const registerMutation = useRegister()
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterValues, unknown, RegisterData>({
    resolver: zodResolver(registerSchema),
    defaultValues: { full_name: '', email: '', password: '', confirm_password: '' },
  })

  // On success the store gets the tokens and PublicOnlyRoute redirects to the board.
  const onSubmit = handleSubmit(({ full_name, email, password }) => {
    registerMutation.mutate({ full_name, email, password })
  })

  return (
    <main className="flex min-h-svh items-center justify-center bg-muted/40 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>
            <h1>Create an account</h1>
          </CardTitle>
          <CardDescription>Sign up to start organising tasks on the board.</CardDescription>
        </CardHeader>
        <CardContent>
          <form noValidate onSubmit={(event) => void onSubmit(event)}>
            <FieldGroup>
              {registerMutation.isError && (
                <Alert variant="destructive">
                  <AlertDescription>
                    {registerErrorMessage(registerMutation.error)}
                  </AlertDescription>
                </Alert>
              )}
              <Field data-invalid={errors.full_name ? true : undefined}>
                <FieldLabel htmlFor="full_name">Full name</FieldLabel>
                <Input
                  autoComplete="name"
                  {...describe('full_name', errors.full_name)}
                  {...register('full_name')}
                />
                <FieldError id="full_name-error" errors={[errors.full_name]} />
              </Field>
              <Field data-invalid={errors.email ? true : undefined}>
                <FieldLabel htmlFor="email">Email</FieldLabel>
                <Input
                  type="email"
                  autoComplete="email"
                  {...describe('email', errors.email)}
                  {...register('email')}
                />
                <FieldError id="email-error" errors={[errors.email]} />
              </Field>
              <Field data-invalid={errors.password ? true : undefined}>
                <FieldLabel htmlFor="password">Password</FieldLabel>
                <Input
                  type="password"
                  autoComplete="new-password"
                  {...describe('password', errors.password, true)}
                  {...register('password')}
                />
                <FieldDescription id="password-hint">
                  {PASSWORD_MIN_LENGTH} or more characters.
                </FieldDescription>
                <FieldError id="password-error" errors={[errors.password]} />
              </Field>
              <Field data-invalid={errors.confirm_password ? true : undefined}>
                <FieldLabel htmlFor="confirm_password">Confirm password</FieldLabel>
                <Input
                  type="password"
                  autoComplete="new-password"
                  {...describe('confirm_password', errors.confirm_password)}
                  {...register('confirm_password')}
                />
                <FieldError id="confirm_password-error" errors={[errors.confirm_password]} />
              </Field>
              <Button type="submit" className="w-full" disabled={registerMutation.isPending}>
                {registerMutation.isPending ? 'Creating account…' : 'Create account'}
              </Button>
              <p className="text-center text-sm text-muted-foreground">
                Already have an account?{' '}
                {/* Keep `state` so a post-sign-in redirect survives switching pages. */}
                <Link
                  to="/login"
                  state={location.state as unknown}
                  className="text-foreground underline underline-offset-4 hover:text-primary"
                >
                  Sign in
                </Link>
              </p>
            </FieldGroup>
          </form>
        </CardContent>
      </Card>
    </main>
  )
}
