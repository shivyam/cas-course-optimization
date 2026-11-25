type OutlineWorkflowStepperProps = {
  currentStep: number
}

const workflowSteps = [
  'Course outline upload',
  'Extracted content and associated fields',
  'Review & approve',
  'Check policy & CEAB',
] as const

function OutlineWorkflowStepper({ currentStep }: OutlineWorkflowStepperProps) {
  return (
    <nav
      aria-label="Course outline workflow"
      className="overflow-x-auto rounded-xl border border-cas-border bg-white px-3 py-2 shadow-sm sm:px-4"
    >
      <ol className="flex min-w-[620px] items-start">
        {workflowSteps.map((title, index) => {
          const isCurrent = index === currentStep
          const isComplete = index < currentStep

          return (
            <li key={title} className="flex min-w-0 flex-1 items-start last:flex-none">
              <div className="flex w-28 shrink-0 flex-col items-center text-center sm:w-36">
                <span
                  aria-current={isCurrent ? 'step' : undefined}
                  className={`flex h-7 w-7 items-center justify-center rounded-full border-2 text-[10px] font-bold ${
                    isCurrent || isComplete
                      ? 'border-mcmaster-maroon bg-mcmaster-maroon text-white'
                      : 'border-cas-border bg-cas-surface text-cas-muted'
                  }`}
                >
                  {index + 1}
                </span>
                <span
                  className={`mt-1 text-[10px] font-semibold leading-3 ${
                    isCurrent ? 'text-mcmaster-maroon' : 'text-cas-muted'
                  }`}
                >
                  {title}
                </span>
              </div>
              {index < workflowSteps.length - 1 && (
                <span
                  aria-hidden="true"
                  className={`mt-3 h-0.5 min-w-6 flex-1 ${
                    isComplete ? 'bg-mcmaster-maroon' : 'bg-cas-border'
                  }`}
                />
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

export default OutlineWorkflowStepper
