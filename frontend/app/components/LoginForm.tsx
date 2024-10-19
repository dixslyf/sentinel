'use client'
import { loginDet } from "../interfaces/general";
import { useRouter } from "next/navigation";


const LoginForm = () =>{
    const router = useRouter();

    async function validateLogin(formdata: FormData){
        const det: loginDet = {
            uname: formdata.get('usr') as string,
            pwd: formdata.get('pwd') as string,
        }

        // The code below is to send data to an external url.
        // To use, uncomment the codes below and replace the ''
        // with the url.
        // No error code for now since there is no status code yet.
        // const res = await fetch('', {
        //     method: 'POST',
        //     headers: { 'Content-Type': 'application/json' },
        //     body: JSON.stringify(det),
        // });

        // if (res.ok){
        //     router.push("/dashboard");
        // } 

        // This is for testing purposes 
        // comment this section if using the top code block.
        if (det){
            router.push('/dashboard');
        }
        

    }

    return (
        <form className="space-y-4 w-2/5 ml-8" action={validateLogin}>
            <div className="text flex justify-start">
                <span
                className="italic font-semibold text-xl w-full text-left font-serif"
                >Begin Your Journey With Sentinel</span>
            </div>
            <div className="uname flex flex-col text-left">
                <label 
                className="text-sm text-gray-500"
                htmlFor="usr">Username</label>
                <input 
                className="border-b-2 focus:outline-none"
                type="text" 
                name="usr" 
                placeholder="Admin" 
                required />
            </div>
            <div className="password flex flex-col text-left">
                <label 
                className="text-sm text-gray-500"
                htmlFor="pwd">Password</label>
                <input 
                className="border-b-2 focus:outline-none"
                type="password" 
                name="pwd" 
                placeholder="************" 
                required />
                </div>
            <div className="submit-btn flex justify-end">
            <button 
                className="text-lg text-white bg-black rounded-xl py-1 px-3"
                type="submit"
                >Log In</button>
            </div>
        </form>
    )
}

export default LoginForm;