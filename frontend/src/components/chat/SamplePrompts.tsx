import { useState } from 'react'

interface SamplePromptsProps {
  onSelectPrompt: (prompt: string) => void
  hidden?: boolean
}

const sampleSections = [
  {
    icon: 'fas fa-prescription-bottle-alt',
    title: 'Ask about drug dosing and interactions',
    prompts: [
      'Calculate the dose for ceftriaxone for a 60kg adult with severe pneumonia',
      'What happens when green leafy vegetables are taken in large amounts while on warfarin?',
    ],
  },
  {
    icon: 'fas fa-book-medical',
    title: 'About Guidelines',
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
    setExpandedSection(expandedSection === title ? null : title)
  }

  return (
    <section className="sample-questions">
      {expandedSection ? (
        <div className="sample-expanded-view">
          <div className="sample-expanded-header">
            <span>{expandedSection}</span>
            <button
              className="sample-close-button"
              onClick={() => setExpandedSection(null)}
            >
              <i className="fas fa-times" />
            </button>
          </div>
          <div className="sample-expanded-list">
            {sampleSections
              .find((section) => section.title === expandedSection)
              ?.prompts.map((prompt, index) => (
                <button
                  key={index}
                  className="sample-prompt-item"
                  onClick={() => {
                    onSelectPrompt(prompt)
                    setExpandedSection(null)
                  }}
                >
                  <span>{prompt}</span>
                  <i className="fas fa-external-link-alt" />
                </button>
              ))}
          </div>
        </div>
      ) : (
        <div className="sample-sections-container">
          {sampleSections.map((section) => (
            <button
              key={section.title}
              className="sample-section-button"
              onClick={() => toggleSection(section.title)}
            >
              <i className={section.icon} />
              <span>{section.title}</span>
            </button>
          ))}
        </div>
      )}
    </section>
  )
}

