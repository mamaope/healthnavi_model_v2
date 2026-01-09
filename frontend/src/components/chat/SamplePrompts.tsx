import { useState } from 'react'

interface SamplePromptsProps {
  onSelectPrompt: (prompt: string) => void
  hidden?: boolean
}

const sampleSections = [
  {
    icon: 'fas fa-prescription-bottle-alt',
    title: 'Drug Dosing & Interactions',
    prompts: [
      'Calculate the dose for ceftriaxone for a 60kg adult with severe pneumonia',
      'What happens when green leafy vegetables are taken in large amounts while on warfarin?',
    ],
  },
  {
    icon: 'fas fa-book-medical',
    title: 'Clinical Guidelines',
    prompts: [
      'What are the ADA (American Diabetes Association) recommendations for initiating insulin therapy in type 2 diabetes?',
      'According to WHO malaria guidelines, how should malaria in pregnancy be treated?',
    ],
  },
  {
    icon: 'fas fa-stethoscope',
    title: 'Treatment Options',
    prompts: [
      'What are the treatment options for severe malnutrition in children under 5?',
      'What is the first-line antihypertensive medication for stage 1 hypertension?',
    ],
  },
]

export function SamplePrompts({ onSelectPrompt, hidden }: SamplePromptsProps) {
  const [expandedSection, setExpandedSection] = useState<string | null>(null)

  if (hidden) {
    return null
  }

  const toggleSection = (title: string) => {
    setExpandedSection((prev) => (prev === title ? null : title))
  }

  return (
    <section className="sample-questions-compact">
      <div className="sample-questions-dropdown">
        {sampleSections.map((section) => {
          const isExpanded = expandedSection === section.title
          return (
            <div key={section.title} className="sample-dropdown-item">
              <button
                type="button"
                className={`sample-dropdown-trigger ${isExpanded ? 'expanded' : ''}`}
                onClick={() => toggleSection(section.title)}
                aria-expanded={isExpanded}
              >
                <i className={section.icon} />
                <span className="sample-dropdown-title">{section.title}</span>
                <i className={`fas fa-chevron-down sample-dropdown-chevron ${isExpanded ? 'expanded' : ''}`} />
              </button>
              {isExpanded && (
                <div className="sample-dropdown-menu">
                  {section.prompts.map((prompt, index) => (
                    <button
                      key={index}
                      type="button"
                      className="sample-dropdown-option"
                      onClick={() => {
                        onSelectPrompt(prompt)
                        setExpandedSection(null)
                      }}
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}

