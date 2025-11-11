interface SamplePromptsProps {
  onSelectPrompt: (prompt: string) => void
  hidden?: boolean
}

const sampleSections = [
  {
    icon: 'fas fa-prescription-bottle-alt',
    title: 'Ask about drug dosing and interactions',
    prompts: [
      {
        icon: 'fas fa-syringe',
        label: 'Calculate the dose for ceftriaxone for a 60kg adult with severe pneumonia',
      },
      {
        icon: 'fas fa-leaf',
        label: 'What happens when green leafy vegetables are taken in large amounts while on warfarin?',
      },
    ],
  },
  {
    icon: 'fas fa-book-medical',
    title: 'About Guidelines',
    prompts: [
      {
        icon: 'fas fa-notes-medical',
        label:
          'What are the ADA (American Diabetes Association) recommendations for initiating insulin therapy in type 2 diabetes?',
      },
      {
        icon: 'fas fa-baby',
        label:
          'According to WHO malaria guidelines, how should malaria in pregnancy be treated?',
      },
    ],
  },
  {
    icon: 'fas fa-stethoscope',
    title: 'Treatment Options',
    prompts: [
      {
        icon: 'fas fa-child',
        label: 'What are the treatment options for severe malnutrition in children under 5?',
      },
      {
        icon: 'fas fa-heartbeat',
        label: 'What is the first-line antihypertensive medication for stage 1 hypertension?',
      },
    ],
  },
]

export function SamplePrompts({ onSelectPrompt, hidden }: SamplePromptsProps) {
  if (hidden) {
    return null
  }

  return (
    <section className="sample-questions">
      <h3>Try these examples:</h3>
      <div className="sample-grid">
        {sampleSections.map((section) => (
          <div key={section.title} className="sample-category">
            <h5>
              <i className={section.icon} /> {section.title}
            </h5>
            {section.prompts.map((prompt) => (
              <button
                key={prompt.label}
                className="sample-question"
                onClick={() => onSelectPrompt(prompt.label)}
              >
                <i className={prompt.icon} />
                <span>{prompt.label}</span>
              </button>
            ))}
          </div>
        ))}
      </div>
    </section>
  )
}

