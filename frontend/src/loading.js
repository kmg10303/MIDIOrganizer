import ReactLoading from 'react-loading'


const loadingBar = ({ type, color }) => (
    <ReactLoading type={type} color={color} height={667} width={375} />
);
 
export default loadingBar;