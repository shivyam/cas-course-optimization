type PageHeaderProps = {
  eyebrow: string
  title: string
  description: string
}

function PageHeader({ eyebrow, title, description }: PageHeaderProps) {
  return (
    <header className="mb-6 space-y-2 sm:mb-8">
      <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-mcmaster-maroon">
        {eyebrow}
      </p>
      <h1 className="text-2xl font-semibold tracking-tight text-cas-ink sm:text-[30px]">
        {title}
      </h1>
      <p className="max-w-4xl text-sm leading-relaxed text-cas-muted sm:text-[14px]">
        {description}
      </p>
    </header>
  )
}

export default PageHeader
