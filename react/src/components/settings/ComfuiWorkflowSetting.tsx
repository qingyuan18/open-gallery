import { Button } from '@/components/ui/button'
import { PaletteIcon, PlusIcon, TrashIcon, UploadIcon } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useRef } from 'react'
import { Input } from '../ui/input'
import { Textarea } from '../ui/textarea'
import { DialogContent, DialogHeader, DialogTitle, Dialog } from '../ui/dialog'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import { authenticatedFetch } from '@/api/auth'

export type ComfyWorkflowInput = {
  name: string
  type: 'string' | 'number' | 'boolean'
  description: string
  node_id: string
  node_input_name: string
  default_value: string | number | boolean
}

export type ComfyWorkflow = {
  id: string
  name: string
  description: string
  api_json: Record<string, any> | null
  inputs: ComfyWorkflowInput[] | null
  // outputs: ComfyWorkflowOutput[]
}

export default function ComfuiWorkflowSetting() {
  const { t } = useTranslation()
  const [showAddWorkflowDialog, setShowAddWorkflowDialog] = useState(false)
  const [workflows, setWorkflows] = useState<ComfyWorkflow[]>([])
  useEffect(() => {
    authenticatedFetch('/api/settings/comfyui/list_workflows')
      .then((res) => res.json())
      .then((data) => {
        console.log('ComfyUI workflows:', data)
        const workflows: ComfyWorkflow[] = data.map((workflow: any) => {
          const inputs = JSON.parse(workflow.inputs ?? [])
          const outputs = JSON.parse(workflow.outputs ?? [])
          const api_json = JSON.parse(workflow.api_json)
          return {
            ...workflow,
            inputs: inputs,
            outputs: outputs,
            api_json: api_json,
          }
        })
        setWorkflows(workflows)
      })
  }, [])
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <PaletteIcon className="w-5 h-5" />
        <p className="text-sm font-bold">{t('settings:comfyui.workflows')}</p>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowAddWorkflowDialog(true)}
        >
          <PlusIcon className="w-4 h-4" />
          Add Workflow
        </Button>
        {showAddWorkflowDialog && (
          <AddWorkflowDialog onClose={() => setShowAddWorkflowDialog(false)} />
        )}
      </div>
      {/* Workflows */}
      {workflows.length > 0 && (
        <div className="space-y-2">
          <div className="grid grid-cols-2 gap-2">
            {workflows.map((workflow) => (
              <div
                key={workflow.id}
                className="flex items-center gap-2 border p-2 rounded-md justify-between"
              >
                <div className="flex flex-col gap-1">
                  <p>{workflow.name}</p>
                  <p className="text-muted-foreground">
                    {workflow.description}
                  </p>
                </div>
                <Button variant="ghost" size="icon">
                  <TrashIcon />
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

type ComfyUIAPINode = {
  class_type: string
  inputs: Record<string, any>
}
function AddWorkflowDialog({ onClose }: { onClose: () => void }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [workflowName, setWorkflowName] = useState('')
  const [workflowJson, setWorkflowJson] = useState<Record<
    string,
    ComfyUIAPINode
  > | null>(null)
  const [inputs, setInputs] = useState<ComfyWorkflowInput[]>([])
  const [error, setError] = useState('')
  const [workflowDescription, setWorkflowDescription] = useState('')
  const [outputs, setOutputs] = useState<
    {
      name: string
      type: 'string' | 'number' | 'boolean'
      description: string
    }[]
  >([])
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputs([])
    const file = e.target.files?.[0]
    if (file) {
      try {
        const fileContent = await file.text()
        // Parse the JSON content
        const jsonContent = JSON.parse(fileContent)
        console.log('Parsed workflow JSON:', jsonContent)
        setWorkflowJson(jsonContent)
        setWorkflowName(file.name.replace('.json', ''))
        for (const key in jsonContent) {
          const node: ComfyUIAPINode = jsonContent[key]
          if (!node.class_type) {
            throw new Error('No class_type found in workflow JSON')
          }
          const classType = node.class_type
          // if (classType === 'SaveImage') {
          //   setOutputs(node.inputs.required.model_name.map((model: string) => ({
          //     name: model,
          //     type: 'string',
          //     description: '',
          //   })))
          // }
        }
      } catch (error) {
        console.error(error)
        toast.error(
          'Invalid workflow JSON, make sure you exprted API JSON in ComfyUI! ' +
            error
        )
      }

      // const formData = new FormData()
      // formData.append('file', file)
      // formData.append('workflow_name', workflowName)

      // await fetch('/api/settings/comfyui/upload_workflow', {
      //   method: 'POST',
      //   body: formData,
      // })
    }
  }
  const handleSubmit = () => {
    if (!workflowJson) {
      setError('Please upload a workflow API JSON file')
      return
    }
    if (inputs.length === 0) {
      setError('Please add at least one input')
      return
    }
    if (workflowName === '') {
      setError('Please enter a workflow name')
      return
    }
    authenticatedFetch('/api/settings/comfyui/create_workflow', {
      method: 'POST',
      body: JSON.stringify({
        name: workflowName,
        api_json: workflowJson,
        description: workflowDescription,
        inputs: inputs,
      }),
    }).then(async (res) => {
      if (res.ok) {
        toast.success('Workflow created successfully')
      } else {
        const data = await res.json()
        toast.error(`Failed to create workflow: ${data.message}`)
      }
    })
  }
  return (
    <Dialog
      open={true}
      onOpenChange={(open) => {
        if (!open) {
          onClose()
        }
      }}
    >
      <DialogContent
        // open={true}
        className="max-w-4xl h-[80vh] overflow-y-auto flex flex-col"
      >
        <DialogHeader>
          <div className="flex items-center gap-2 justify-between">
            <DialogTitle>Add Workflow</DialogTitle>
            <Button onClick={handleSubmit}>Submit</Button>
          </div>
          {error && <p className="text-red-500">{error}</p>}
        </DialogHeader>
        <Input
          type="text"
          style={{ flexShrink: 0 }}
          placeholder="Workflow Name"
          value={workflowName}
          onChange={(e) => setWorkflowName(e.target.value)}
        />
        <Textarea
          placeholder="Workflow Description"
          value={workflowDescription}
          onChange={(e) => setWorkflowDescription(e.target.value)}
        />
        <Button onClick={() => inputRef.current?.click()} variant={'outline'}>
          <UploadIcon className="w-4 h-4 mr-2" />
          Upload Workflow API JSON
        </Button>
        <input
          type="file"
          accept=".json"
          ref={inputRef}
          onChange={handleFileChange}
          className="hidden"
        />
        {workflowJson && (
          <div className="flex flex-col bg-accent p-2 rounded-md">
            <p className="font-bold mb-2">Inputs</p>
            <div className="ml-1">
              {inputs.length > 0 ? (
                inputs.map((input) => (
                  <div key={input.name} className="flex items-center gap-2">
                    <div className="flex flex-col gap-1 flex-1">
                      <input
                        type="text"
                        value={input.name}
                        placeholder="Input Name"
                        onChange={(e) => {
                          setInputs(
                            inputs.map((i) =>
                              i.name === input.name
                                ? { ...i, name: e.target.value }
                                : i
                            )
                          )
                        }}
                        className="border-none bg-transparent w-full"
                      />
                      <Input
                        type="text"
                        value={input.default_value.toString()}
                        disabled
                      />
                      <textarea
                        placeholder="Please enter your description of the input"
                        value={input.description}
                        className="border-none bg-transparent w-full"
                        onChange={(e) => {
                          setInputs(
                            inputs.map((i) =>
                              i.name === input.name
                                ? { ...i, description: e.target.value }
                                : i
                            )
                          )
                        }}
                      />
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => {
                        setInputs(inputs.filter((i) => i.name !== input.name))
                      }}
                    >
                      <TrashIcon className="w-4 h-4" />
                    </Button>
                  </div>
                ))
              ) : (
                <p className="text-sm text-muted-foreground text-center">
                  Please add your workflow inputs from below. Choose at lease
                  one input.
                </p>
              )}
            </div>
            {/* <p className="font-bold">Outputs</p>
              {outputs.map((input) => (
                <div key={input.name}>
                  <p>{input.name}</p>
                  <p>{input.description}</p>
                </div>
              ))} */}
          </div>
        )}
        {workflowJson &&
          Object.keys(workflowJson).map((nodeID) => {
            const node = workflowJson[nodeID]
            return (
              <div key={nodeID}>
                <p className="font-bold">
                  {node.class_type} #{nodeID}
                </p>
                <div className="ml-4 flex flex-col gap-1">
                  {Object.keys(node.inputs).map((inputKey) => {
                    const inputValue = node.inputs[inputKey]
                    if (
                      typeof inputValue !== 'boolean' &&
                      typeof inputValue !== 'number' &&
                      typeof inputValue !== 'string'
                    ) {
                      return null
                    }
                    return (
                      <div key={inputKey} className="flex items-center gap-2">
                        <p className="bg-accent text-sm px-2 py-0.5 rounded-md">
                          {inputKey}
                        </p>
                        <Input
                          type="text"
                          value={inputValue.toString()}
                          disabled
                        />
                        <Button
                          variant="outline"
                          size="default"
                          onClick={() => {
                            setInputs([
                              ...inputs.filter(
                                (i) =>
                                  i.node_id !== nodeID ||
                                  i.node_input_name !== inputKey
                              ),
                              {
                                name: inputKey,
                                type: typeof inputValue as
                                  | 'string'
                                  | 'number'
                                  | 'boolean',
                                description: '',
                                node_id: nodeID,
                                node_input_name: inputKey,
                                default_value: inputValue,
                              },
                            ])
                          }}
                        >
                          <PlusIcon className="w-4 h-4" />
                          Add Input
                        </Button>
                      </div>
                    )
                  })}
                </div>
              </div>
            )
          })}
      </DialogContent>
    </Dialog>
  )
}
