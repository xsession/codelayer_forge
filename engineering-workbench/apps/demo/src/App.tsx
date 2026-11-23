import { Workbench } from '@ew/workbench-ui';
import { exampleElectronicsPlugin } from '@plugins/example-electronics';
import { demoProject } from './demoProject';
import './styles.css';

export default function App() {
  return <Workbench initialProject={demoProject} initialDiagramId="diagram-top" plugins={[exampleElectronicsPlugin]} />;
}
