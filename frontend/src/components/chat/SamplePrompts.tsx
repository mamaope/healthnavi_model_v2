import { useState } from 'react'

interface SamplePromptsProps {
  onSelectPrompt: (prompt: string) => void
  hidden?: boolean
}

const sampleSections = [
  {
    icon: 'fas fa-prescription-bottle-alt',
    title: 'Drug Dosing & Interactions',
    description: '',
    prompts: [
      'Calculate the dose for ceftriaxone for a 60kg adult with severe pneumonia',
      'What happens when green leafy vegetables are taken in large amounts while on warfarin?',
    ],
  },
  {
    icon: 'fas fa-book-medical',
    title: 'Clinical Guidelines',
    description: '',
    prompts: [
      'What are the ADA (American Diabetes Association) recommendations for initiating insulin therapy in type 2 diabetes?',
      'According to WHO malaria guidelines, how should malaria in pregnancy be treated?',
    ],
  },
  {
    icon: 'fas fa-stethoscope',
    title: 'Treatment Options',
    description: '',
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
      <div className="sample-accordion">
        {sampleSections.map((section) => {
          const isExpanded = expandedSections.has(section.title)
          return (
            <div key={section.title} className="sample-accordion-item">
              <button
                type="button"
                className={`sample-accordion-header ${isExpanded ? 'expanded' : ''}`}
                onClick={() => toggleSection(section.title)}
                aria-expanded={isExpanded}
              >
                <div className="sample-accordion-header-content">
                  <i className={section.icon} />
                  <div className="sample-accordion-title-group">
                    <span className="sample-accordion-title">{section.title}</span>
                    <span className="sample-accordion-description">{section.description}</span>
                  </div>
                </div>
                <i className={`fas fa-chevron-down sample-accordion-chevron ${isExpanded ? 'expanded' : ''}`} />
              </button>
              <div className={`sample-accordion-content ${isExpanded ? 'expanded' : ''}`}>
                <div className="sample-accordion-prompts">
                  {section.prompts.map((prompt, index) => (
                    <button
                      key={index}
                      type="button"
                      className="sample-prompt-card"
                      onClick={() => {
                        onSelectPrompt(prompt)
                        setExpandedSections(new Set())
                      }}
                    >
                      <i className="fas fa-arrow-right" />
                      <span>{prompt}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}

