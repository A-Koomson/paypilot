import { Link } from 'react-router-dom'
import { Compass } from 'lucide-react'
import { Container, EmptyState, buttonStyles } from '@/components/ui'

export function NotFoundPage() {
  return (
    <Container className="py-16">
      <EmptyState
        icon={Compass}
        title="Page not found"
        description="The page you’re looking for doesn’t exist or has moved."
        action={
          <Link to="/" className={buttonStyles()}>
            Back to home
          </Link>
        }
      />
    </Container>
  )
}
