import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Toaster } from "@/components/ui/sonner";
import DayView from "./DayView.jsx";
import TemplateEditor from "./TemplateEditor.jsx";
import OutcomesView from "./OutcomesView.jsx";

export default function App() {
  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <h1 className="mb-6 text-2xl font-semibold tracking-tight">Make the Hours</h1>
      <Tabs defaultValue="day">
        <TabsList className="mb-4">
          <TabsTrigger value="day">Day</TabsTrigger>
          <TabsTrigger value="template">Template</TabsTrigger>
          <TabsTrigger value="outcomes">Outcomes</TabsTrigger>
        </TabsList>
        <TabsContent value="day">
          <DayView />
        </TabsContent>
        <TabsContent value="template">
          <TemplateEditor />
        </TabsContent>
        <TabsContent value="outcomes">
          <OutcomesView />
        </TabsContent>
      </Tabs>
      <Toaster richColors position="top-center" />
    </div>
  );
}
