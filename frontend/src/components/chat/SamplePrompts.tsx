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
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set())

  if (hidden) {
    return null
  }

  const toggleSection = (title: string) => {
    setExpandedSections((prev) => {
      const newSet = new Set(prev)
      if (newSet.has(title)) {
        newSet.delete(title)
      } else {
        newSet.add(title)
      }
      return newSet
    })
  }

  return (
    <section className="sample-questions-modern">
      <div className="sample-questions-grid">
        {sampleSections.map((section) => {
          const isExpanded = expandedSections.has(section.title)
          return (
            <div key={section.title} className="sample-question-card">
              <button
                type="button"
                className={`sample-question-header ${isExpanded ? 'expanded' : ''}`}
                onClick={() => toggleSection(section.title)}
                aria-expanded={isExpanded}
              >
                <div className="sample-question-icon-wrapper">
                  <i className={section.icon} />
                </div>
                <span className="sample-question-title">{section.title}</span>
                <i className={`fas fa-chevron-down sample-question-chevron ${isExpanded ? 'expanded' : ''}`} />
              </button>
              <div className={`sample-question-content ${isExpanded ? 'expanded' : ''}`}>
                {section.prompts.map((prompt, index) => (
                  <button
                    key={index}
                    type="button"
                    className="sample-question-item"
                    onClick={() => {
                      onSelectPrompt(prompt)
                      setExpandedSections(new Set())
                    }}
                  >
                    <span className="sample-question-text">{prompt}</span>
                    <i className="fas fa-arrow-right" />
                  </button>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}

